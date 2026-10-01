#!/usr/bin/env python3
"""aria2 on-download-complete 钩子：把媒体暂存区里的条目录入库。

aria2 调用时会传 3 个参数：gid、文件数、第一个文件路径（这里只用 gid）。
只有任务目录位于 <媒体库根>/.incoming/{Movies,TV,Private,_unsorted}（A2_MEDIA_ROOT 配置）时才动作
——电影/剧集的判断在 a2 add 时就完成了，编码在暂存子目录里；只有 _unsorted 才二次判断。

完成判据必须问 aria2，不能看 <条目>.aria2 控制文件在不在（踩过坑，勿回退）：
  1) conf 里 force-save=true 让 aria2 在"下载完成/移除"后照旧保存控制文件 —— 完成几小时后
     .aria2 仍躺在暂存区；
  2) aria2 触发本钩子的顺序是「下载完成 → 保存片段文件 → 执行钩子」，钩子运行时控制文件必然存在。
  于是"有同名控制文件 ⇒ 仍在下载"恒为真，BT 剧集全部被跳过、永久卡在 .incoming。
改为查 RPC（tellActive/tellWaiting/tellStopped）：
  - busy：仍被未完成任务占用的 (任务目录, 顶层条目) —— active/waiting，以及停在 stopped 的 error/paused；
  - done：数据已完整（completedLength == totalLength > 0）的条目，含本次 gid 与 stopped 里的 complete 任务。
  条目必须在 done 里才搬：只在 busy 里跳过；哪边都不在（aria2 结果列表已被清空/重启丢失）也跳过并记日志，
  宁可由人确认，也不要靠"没有控制文件"去猜——实测这样会把没下完的 mp4 搬进媒体库。
搬之前再用 ffprobe 兜一道：条目里最大的视频文件解析不出来就不搬（挡住尾部截断的容器）。
  RPC 查询失败时整轮不搬（宁可留到下轮，也不要在状态未知时动手）。
另外照旧挡掉两类"假完成"：<hash>.torrent 与 [METADATA]* 一律跳过。
普通下载（conf 的默认下载目录，如 ${A2_DOWNLOAD_DIR:-~/Downloads}）直接静默退出。日志：~/.aria2/move.log
入库时会调用 nameclean.clean_name() 清洗站点广告（去网址/"地址发布页"之类），
只削广告片段，不动 SxxExx/年份/分辨率这些刮削要用的信息；目录内部也洗（最多两层）。
"""
import fcntl, json, os, re, shutil, subprocess, sys, time, urllib.error, urllib.request

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
try:
    from nameclean import clean_name, clean_tree       # 入库文件名清洗（去站点广告）
except Exception:                                        # 模块缺失也要能正常入库
    def clean_name(n):
        return n

    def clean_tree(path, depth=2, log=None):
        return []

TB = os.path.expanduser(os.environ.get("A2_MEDIA_ROOT", "~/media"))   # 媒体库根（含 Movies/TV/Private，用户自建）
STAGING = TB + "/.incoming"
LIB = {"Movies": TB + "/Movies", "TV": TB + "/TV", "Private": TB + "/Private"}
UNSORTED = "_unsorted"
VIDEO_EXT = (".mkv", ".mp4", ".avi", ".ts", ".m2ts", ".mov", ".wmv", ".flv",
             ".rmvb", ".mpg", ".m4v")
TV_RE = re.compile(r"(?i)(s\d{1,2}[\s._-]*e\d{1,3}|(?<!\d)\d{1,2}x\d{2}(?!\d)|"
                   r"第\s?[\d一二三四五六七八九十]{1,3}\s?[-~—至]?\s?[\d一二三四五六七八九十]{0,3}\s?[集話话期季]|"
                   r"[全共]\s?[\d一二三四五六七八九十]{0,4}\s?[集季]|合集|season[\s._-]?\d|"
                   r"\bep\s?\d{1,3}\b)")
QUALITY_RE = re.compile(r"(?i)(\b(19|20)\d{2}\b|1080p|2160p|720p|480p|\b4k\b|blu-?ray|"
                        r"web-?dl|webrip|hdtv|remux|hdr|dvdrip|bdrip)")


def volume_ok(path):
    """目标盘当前可用吗（跨平台）：目录存在可写，或能创建在非系统盘上。见 path_target_ok。"""
    ok, why = path_target_ok(path)
    if not ok:
        LAST_PATH_REASON[0] = why
    return ok



# ---------- 跨平台小工具（macOS / Linux / Windows 通用，不做任何系统特有假设）----------

def _same_device(a, b):
    """两个路径是否在同一存储设备上（POSIX 看 st_dev；Windows 上 st_dev 是卷标识）。"""
    try:
        return os.stat(a).st_dev == os.stat(b).st_dev
    except OSError:
        return False


def path_target_ok(path):
    """目标路径当前能不能用。返回 (ok, 原因)。

    放行：
      - 路径已存在（是目录时要求可写）；
      - 路径在**家目录内**（把媒体库放系统盘上是正常选择）；
      - 路径落在与家目录**不同的存储设备**上（外接盘/网络盘/另一个分区，OK）；
      - 显式设了 A2_ALLOW_CREATE=1。
    拒绝：
      - 路径不存在、又既不在家目录内、还会被创建在**家目录所在的那块盘**上 ——
        这正是外接盘/网络盘没挂载时挂载点目录消失的样子（例：/mnt/usb/media、D:\media、
        以及任意"挂载点凭空消失"的场景），继续下去会把几十 GB 悄悄写进系统盘。

    判据只用 st_dev 与家目录比较（POSIX 与 Windows 都成立），不写死任何平台的挂载点前缀。
    """
    p = os.path.abspath(os.path.expanduser(path))
    if os.path.exists(p):
        if os.path.isdir(p) and not os.access(p, os.W_OK):
            return False, "%s 存在但不可写" % p
        return True, ""
    if os.environ.get("A2_ALLOW_CREATE") == "1":
        return True, ""
    home = os.path.abspath(os.path.expanduser("~"))
    if p == home or p.startswith(home.rstrip(os.sep) + os.sep):
        return True, ""                                     # 家目录内：系统盘也放行
    anc = p
    while not os.path.exists(anc):
        parent = os.path.dirname(anc)
        if not parent or parent == anc:
            break
        anc = parent
    if not os.path.exists(anc):
        return False, "%s 所在位置不可用（盘符/挂载点不存在）" % p
    if not _same_device(anc, home):
        return True, ""                                     # 落在别的盘上：放行
    return False, ("%s 不存在，且会被创建到系统盘上（外接盘/网络盘多半没挂载）" % p)

HINT_CREATE = ("若该路径本来就该建在系统盘上：先 mkdir -p 它，或设 A2_ALLOW_CREATE=1 再试。")


LAST_PATH_REASON = [""]


def classify(name):
    """按名字判断 'TV' / 'Movies' / None（与 a2 的规则保持一致）。"""
    if TV_RE.search(name):
        return "TV"
    if name.lower().endswith(VIDEO_EXT) or QUALITY_RE.search(name):
        return "Movies"
    return None

FFPROBE_CANDIDATES = (
    "/opt/homebrew/bin/ffprobe",
    "/usr/local/bin/ffprobe", "/usr/bin/ffprobe",
    "/snap/bin/ffprobe", "/var/lib/flatpak/exports/bin/ffprobe",
    os.path.join(os.path.expanduser("~"), "scoop", "shims", "ffprobe.exe"),
    r"C:\ProgramData\chocolatey\bin\ffprobe.exe",
    r"C:\Program Files\ffmpeg\bin\ffprobe.exe",
)

CONF = os.path.expanduser("~/.aria2/aria2.conf")
LOG = os.path.expanduser("~/.aria2/move.log")
LOCK = os.path.expanduser("~/.aria2/move.lock")
FIELDS = ["gid", "status", "dir", "completedLength", "totalLength", "files"]


def acquire_lock(timeout=180):
    """跨进程互斥：多个任务几乎同时完成时 aria2 会并发调用本钩子，两个实例同时扫同一目录会互相踩
    （日志里表现为一条"入库"紧跟一条 rename 的 No such file）。"""
    try:
        fh = open(LOCK, "a")
    except OSError as exc:
        log("打不开锁文件 %s: %s" % (LOCK, exc))
        return None
    deadline = time.time() + timeout
    while True:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fh
        except OSError:
            if time.time() >= deadline:
                fh.close()
                return None
            time.sleep(1)


def conf_get(key, default):
    try:
        with open(CONF) as fh:
            for line in fh:
                line = line.strip()
                if line.startswith(key + "="):
                    return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return default


def log(msg):
    try:
        with open(LOG, "a") as fh:
            fh.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except OSError:
        pass


def rpc(method, params):
    secret = conf_get("rpc-secret", "")
    port = conf_get("rpc-listen-port", "6800")
    body = json.dumps({"jsonrpc": "2.0", "id": "hook", "method": method,
                       "params": ["token:%s" % secret] + params}).encode()
    req = urllib.request.Request("http://127.0.0.1:%s/jsonrpc" % port, data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=10).read())["result"]
    except urllib.error.HTTPError as exc:
        raise RuntimeError(json.loads(exc.read()).get("error", {}).get("message", str(exc)))


def is_done(task):
    """数据是否已下齐（对 BT 就是所有片段都到齐，无论是否还在做种）。"""
    try:
        total = int(task.get("totalLength") or 0)
        done = int(task.get("completedLength") or 0)
    except (TypeError, ValueError):
        return False
    return total > 0 and done >= total


def top_entries(task):
    """任务占用的顶层条目：返回 (任务目录, {条目名})，条目名是相对 dir 的第一段路径。"""
    d = (task.get("dir") or "").rstrip("/")
    out = set()
    for f in task.get("files") or []:
        p = f.get("path") or ""
        if not p:
            continue
        if p == d:
            out.add(os.path.basename(p))
        elif p.startswith(d + "/"):
            out.add(p[len(d) + 1:].split("/")[0])
    return d, out


def snapshot():
    """→ (busy, done)：busy 是 {条目: 原因}，done 是 {条目}；键均为 (任务目录, 顶层条目)。
    查询失败返回 (None, None)，调用方据此不做任何搬移。"""
    busy, done = {}, set()
    try:
        tasks = (rpc("aria2.tellActive", [FIELDS])
                 + rpc("aria2.tellWaiting", [0, 1000, FIELDS])
                 + rpc("aria2.tellStopped", [0, 1000, FIELDS]))
    except Exception as exc:                             # noqa: BLE001
        log("查询任务列表失败，本轮不搬移: %s" % exc)
        return None, None
    for t in tasks:
        d, entries = top_entries(t)
        if is_done(t):
            done |= {(d, e) for e in entries}
            continue
        reason = ("仍在下载" if t.get("status") in ("active", "waiting")
                  else "任务未完成（%s），保留待处理" % (t.get("status") or "?"))
        for e in entries:
            busy.setdefault((d, e), reason)
    return busy, done


def ffprobe_path():
    """ffprobe 必须按绝对路径兜底找：服务管理器拉起的进程 PATH 很窄
    （macOS launchd 里没有 Homebrew，Linux systemd --user 里常没有 /usr/local/bin），
    shutil.which 会返回 None 并让完整性守卫静默消失（踩过）。找不到只记一次日志。"""
    for c in ([shutil.which("ffprobe")] + list(FFPROBE_CANDIDATES)):
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    if not getattr(ffprobe_path, "_warned", False):
        log("警告：没找到 ffprobe，本次及后续搬移将不做完整性校验（PATH=%s）" % os.environ.get("PATH", ""))
        ffprobe_path._warned = True
    return None


def verify_media(path):
    """搬移前的完整性守卫：条目里最大的视频文件必须能被 ffprobe 解析。
    返回 None 表示通过（或无法判定），否则返回原因字符串。"""
    probe = ffprobe_path()
    if not probe:
        return None
    if os.path.isdir(path):
        files = []
        for root, _dirs, names in os.walk(path):
            for nm in names:
                if nm.lower().endswith(VIDEO_EXT):
                    fp = os.path.join(root, nm)
                    try:
                        files.append((os.path.getsize(fp), fp))
                    except OSError:
                        pass
        if not files:
            return None
    elif path.lower().endswith(VIDEO_EXT):
        files = [(os.path.getsize(path), path)]
    else:
        return None
    biggest = max(files)[1]
    try:
        r = subprocess.run([probe, "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=nw=1:nk=1", biggest],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
    except Exception as exc:                             # noqa: BLE001
        return "ffprobe 没能跑起来: %s" % exc
    if r.returncode != 0 or not r.stdout.strip():
        err = (r.stderr.decode("utf-8", "replace").strip().splitlines() or
               ["exit=%d" % r.returncode])[-1]
        return "ffprobe 校验不过（文件可能不完整）: %s" % err
    return None


def main(argv):
    gid = argv[1] if len(argv) > 1 else ""
    if not gid:
        return 0
    if not volume_ok(TB):
        log("媒体库当前不可用（%s），跳过 gid=%s" % (LAST_PATH_REASON[0], gid))
        return 0
    try:
        st = rpc("aria2.tellStatus", [gid, FIELDS])
    except Exception as exc:                             # noqa: BLE001
        log("查询 gid=%s 失败: %s" % (gid, exc))
        return 0
    d = (st.get("dir") or "").rstrip("/")
    if not d.startswith(STAGING + "/"):
        return 0                                  # 普通下载，不关我们的事
    cat = os.path.basename(d)
    if cat not in LIB and cat != UNSORTED:
        log("暂存目录不在预期分类里，跳过: %s" % d)
        return 0
    lock = acquire_lock()                        # 并发钩子互斥，见 acquire_lock 注释
    if lock is None:
        log("另一个钩子实例还在忙（%s），本轮跳过 gid=%s" % (LOCK, gid))
        return 0
    busy, done = snapshot()
    if busy is None:
        return 0
    if is_done(st):                               # 本次 gid 的数据已下齐 → 它的条目直接放行
        d0, own = top_entries(st)
        done |= {(d0, e) for e in own}
        log("gid=%s status=%s 数据已完整，允许入库" % (gid, st.get("status")))
    n = 0
    for entry in sorted(os.listdir(d)):
        if entry.endswith((".aria2", ".aria2__temp")):
            continue
        if entry.endswith(".torrent") or entry.startswith("[METADATA]"):
            log("跳过 BT 元数据文件: %s" % entry)     # 这些是 aria2 抓元数据的产物，不是内容
            continue
        key = (d, entry)
        if key in done:
            pass                                  # aria2 认定数据已完整 → 放行
        elif key in busy:
            log("跳过（%s）: %s" % (busy[key], entry))
            continue
        else:
            log("跳过（aria2 里找不到对应的完整任务，可能已从结果列表清除，保留待人工确认）: %s" % entry)
            continue
        target = cat
        if cat == UNSORTED:
            target = classify(entry)
            if not target:
                log("无法判断电影/剧集，留在 _unsorted: %s" % entry)
                continue
        src = os.path.join(d, entry)
        bad = verify_media(src)
        if bad:
            log("跳过（%s）: %s" % (bad, entry))
            continue
        wanted = clean_name(entry)
        if wanted != entry:
            log("清洗文件名: %s -> %s" % (entry, wanted))
        dst = os.path.join(LIB[target], wanted)
        if os.path.exists(dst):
            dst = "%s.%d" % (dst, int(time.time()))
        try:
            os.rename(src, dst)
        except OSError as exc:
            log("移动失败 %s -> %s : %s" % (src, dst, exc))
            continue
        log("入库 %s -> %s (gid=%s, %s)" % (src, dst, gid, target))
        clean_tree(dst, log=log)          # 目录内部（最多两层）也洗一遍广告词
        n += 1
    if n:
        log("gid=%s 共移动 %d 个条目" % (gid, n))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
