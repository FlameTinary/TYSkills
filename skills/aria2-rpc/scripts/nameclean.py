#!/usr/bin/env python3
"""入库文件名清洗：去掉站点广告/网址/引流话术，保留识别用的信息。

设计原则（为什么这么保守）
  * 只削「明显不是内容标识」的东西：含域名的括号块、裸网址、引流话术、几个盗版站名。
  * 绝不动：SxxExx / 1x02 / 第N季 / 第N集 / 全N集 / 年份 / 1080p / x265 / AC3 / 中文字幕 /
    音轨语言 / 发布组名 —— Jellyfin 靠这些做刮削，动了就认不出来。
  * 清洗后如果变空、或只剩标点，就放弃清洗（返回原名），宁可丑也不要把名字弄没。
  * 只改名的最后一段（basename）的“正文”，扩展名原样保留。

被 on-complete.py（入库钩子）和 a2 sweep 共用。
"""
import os
import re

# ---------------------------------------------------------------- 可调参数
# 站点名/引流词。加词原则：正常片名里几乎不可能出现的词。
SITE_WORDS = (
    "6v电影", "6v123", "电影天堂", "阳光电影", "飘花电影", "高清剧集网", "BT天堂", "bt天堂",
    "最新电影", "最新地址", "地址发布页", "地址發布頁", "发布页", "發布頁",
    "收藏不迷路", "收藏本站", "永久域名", "防走失", "回家不迷路", "请牢记", "请记住",
    "本站域名", "本站网址", "本站", "域名", "免费观看", "在线观看", "迅雷下载",
)
# 只认这些顶级域，避免把 "Movie.2010.mkv" 之类的误判成网址
TLD = ("com|net|org|cn|cc|tv|xyz|top|vip|info|me|io|la|site|club|online|app|pro|link")
# 结尾的 / 也一起吃掉，免得留下 "http://x.com/File.mkv" 里的斜杠
URL = r"(?:https?://)?(?:www\.)?[A-Za-z0-9][A-Za-z0-9.\-]{0,60}\.(?:%s)(?:\.[A-Za-z]{2,4})?/?" % TLD

# 明确认识的后缀（认不出来就不拆扩展名，整串当正文清洗）
KNOWN_EXT = (".mkv", ".mp4", ".avi", ".ts", ".m2ts", ".mov", ".wmv", ".flv", ".rmvb",
             ".mpg", ".m4v", ".iso", ".zip", ".rar", ".7z", ".srt", ".ass", ".ssa",
             ".sub", ".idx", ".nfo", ".jpg", ".png")

_BRACKET = re.compile(r"[\[【(（][^\]】)）]{0,120}?(?:%s)[^\]】)）]{0,120}?[\]】)）]" % URL)
_URL = re.compile(URL)
_PHRASE = re.compile("|".join(map(re.escape, SITE_WORDS)))


def _split_ext(name):
    root, ext = os.path.splitext(name)
    if ext.lower() in KNOWN_EXT:
        return root, ext
    return name, ""


def clean_name(name):
    """返回清洗后的名字；判断不出或清洗后会变空就原样返回。"""
    if not name:
        return name
    root, ext = _split_ext(name)
    body = root
    for _ in range(3):                       # 反复几轮，处理嵌套的括号/网址
        new = _BRACKET.sub(" ", body)
        new = _URL.sub(" ", new)
        new = _PHRASE.sub(" ", new)
        new = re.sub(r"\s{2,}", " ", new)
        new = re.sub(r"[/\\]+", " ", new)          # 网址被摘掉后剩下的路径斜杠
        new = re.sub(r"\.\s*\.", ".", new)         # 摘掉中间词后留下的 ".." 收敛成一个
        new = re.sub(r"\s+([,，;；:：)\]】])", r"\1", new)
        new = re.sub(r"([\[(【（])\s+", r"\1", new)
        new = re.sub(r"\s*[|｜]\s*$", "", new)
        new = new.strip(" \t\r\n.-_·、,，;；")
        if new == body:
            break
        body = new
    body = re.sub(r"\s{2,}", " ", body).strip()
    if not body or not re.search(r"[^\W_]", body, re.UNICODE):
        return name                            # 清完只剩空/标点 -> 放弃
    return body + ext


def clean_tree(path, depth=2, log=None, _rec=0):
    """把一个已入库的目录/文件的内部名字也清洗一遍（最多 depth 层）。返回改名清单。"""
    out = []
    if not os.path.isdir(path) or _rec >= depth:
        return out
    for child in sorted(os.listdir(path)):
        src = os.path.join(path, child)
        new = clean_name(child)
        dst = src
        if new != child:
            dst = os.path.join(path, new)
            if os.path.exists(dst):
                out.append((src, dst, "目标已存在，跳过"))
                continue
            try:
                os.rename(src, dst)
            except OSError as exc:
                out.append((src, dst, str(exc)))
                continue
            out.append((src, dst, "ok"))
            if log:
                log("内部改名 %s -> %s" % (child, new))
        out.extend(clean_tree(dst, depth, log, _rec + 1))
    return out
