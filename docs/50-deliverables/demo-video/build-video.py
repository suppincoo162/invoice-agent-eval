# -*- coding: utf-8 -*-
"""构建非录屏版演示视频：TTS（带重试）+ 静态卡缓慢推近 + 烧字幕。"""
import sys, json, subprocess, pathlib, asyncio, time, textwrap
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import edge_tts

import os
FF = os.environ.get("FFMPEG", "ffmpeg")
FP = os.environ.get("FFPROBE", "ffprobe")
DEMO = pathlib.Path(__file__).resolve().parent; SL = DEMO / "slides"
OUT = pathlib.Path(os.environ.get("BUILD_DIR", DEMO / ".build")); OUT.mkdir(parents=True, exist_ok=True)
SHOTS = OUT / "shots"; SHOTS.mkdir(parents=True, exist_ok=True)
W, H, FPS = 1920, 1080, 30

SEGS = [
 ("s1","s1.png","这是我们的参赛作品：AI 开票 Agent 版本评测器，版本 v0.3.0。它要回答的不是 Agent 会不会开票，而是——两个版本的执行轨迹，哪一个更值得上线。"),
 ("s2","s2.png","先说问题。如果只看成功率，一个 Agent 没完成任务，可能是两件完全不同的事：一种是它在向用户追问补充信息，任务没完成，但这是正确行为；另一种是金额算错了，却真的把发票开了出去。两种都叫没成功，后果却差一个量级。"),
 ("s3","s3.png","架构上分两层。内层是确定性规则：金额口径与计算、确认前置、重复风险、合法流程转移、工具结果与回调，全部由代码判定，同一输入永远同一结果。外层是可选的大模型独立审计：它只读原始轨迹，不读我们的评测结果，输出还要过一遍契约校验。正式评分只由内层产生——关掉模型，输出完全不变。"),
 ("s4","s4.png","这是验证集里的一个例子，INV-V07。B-05 采集金额时，应该是一千元不含税、六十元税额、一千零六十元含税，实际算成了一千、六十六、一千零六十六。这个错误一路传播：B-08 提交、B-09 回调成功、B-10 生成发票。首错是 B-05。旧的固定扣分账本给七十分，因为它只按根因标签扣一次分；而影响感知的 Rubric 会问一句——错误金额是不是真的开出去了？是，于是封顶二十分。这里差的五十分，就是只算错和真开票的差别。"),
 ("s5","card-v08.png","第二个例子，INV-V08。A 版本在确认预览时给出的是含税三千七百一十元，用户的确认也是基于这个值；但提交时实际传出去的是三千七百一十一元。预览和提交不一致，首错是 A-08，也就是提交这一步。这类错误在只看成功率的报表里看不出来，因为最终发票确实开出来了。"),
 ("s6","card-four-source.png","我们同时跑了四个源：确定性评测、人工复核、本地模型、云端模型。注意两件事：第一，我们不做多数投票；第二，本地小模型在 INV-V04 上输出了非法结论，被程序契约拒绝——我们把它作为事实保留，而不是丢掉。"),
 ("s7","card-package.png","这是提交物：结果 JSONL、自包含的源码包、五阶段验证报告、版本清单与校验和。评审拿到这个包，可以直接复跑。"),
 ("s8","s5.png","验证部分：一百二十八个测试、训练集二十八个 run、验证集十六个 run；官方格式校验通过；同一输入跑两次，输出逐字节相同。"),
 ("s9","s6.png","最后是边界。验证集没有官方逐 run 标签，人工复核是我们的独立判断；跨领域的规则层仍然耦合；反事实归因目前只有设计。我们把这些写清楚，因为不把能力边界说大，本身也是可复现的一部分。"),
]

def dur(p):
    r = subprocess.run([FP,"-v","error","-show_entries","format=duration","-of","default=nw=1:nk=1",str(p)],capture_output=True,text=True)
    return float(r.stdout.strip())

def tts_with_retry(text, path, tries=8):
    if path.exists() and path.stat().st_size > 5000: return
    for a in range(tries):
        try:
            asyncio.run(edge_tts.Communicate(text, voice="zh-CN-YunxiNeural", rate="-4%").save(str(path)))
            return
        except Exception as e:
            print(f"    重试 {a+1}/{tries}: {type(e).__name__}"); time.sleep(6)
    raise SystemExit(f"TTS 失败: {path}")

manifest = []
for sid, img, text in SEGS:
    mp3 = OUT / f"{sid}.mp3"
    tts_with_retry(text, mp3)
    d = dur(mp3)
    manifest.append({"id": sid, "image": str(SL / img), "audio": str(mp3), "duration": d, "text": text})
    print(f"  [tts] {sid}: {d:.2f}s")
(OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

def split_caption(text, limit=34):
    parts, buf = [], ""
    for ch in text:
        buf += ch
        if ch in "。；！？" and len(buf) >= 8: parts.append(buf); buf = ""
        elif len(buf) >= limit: parts.append(buf); buf = ""
    if buf.strip(): parts.append(buf)
    return [p.strip() for p in parts if p.strip()]

def ts(t):
    h=int(t//3600); m=int(t%3600//60); s=t%60
    return f"{h}:{m:02d}:{s:05.2f}"

head = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,Microsoft YaHei,54,&H00222A3B,&H00FFFFFF,&H00FFFFFF,&H00000000,-1,0,0,0,100,100,0,0,1,3,1,2,110,110,78,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"""
lines = [head]; t0 = 0.0; PAD = 0.55; timeline = []
for s in manifest:
    d = s["duration"] + PAD
    chunks = split_caption(s["text"]); total = sum(len(c) for c in chunks) or 1
    ct = t0 + 0.35
    for c in chunks:
        cd = (s["duration"] - 0.35) * (len(c) / total)
        body = r"\N".join(textwrap.wrap(c, width=20)[:3])
        lines.append(f"Dialogue: 0,{ts(ct)},{ts(min(ct+cd,t0+s['duration']))},Caption,,0,0,0,,{body}")
        ct += cd
    timeline.append({"id":s["id"],"dur":round(d,2),"image":s["image"],"audio":s["audio"]})
    t0 += d
(OUT/"subs.ass").write_text("\n".join(lines)+"\n", encoding="utf-8")
print(f"  [ass] {len(lines)-8} 条字幕 / 总长 {t0:.1f}s")

def run(cmd, name, cwd=None):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=cwd)
    if r.returncode != 0:
        print(f"  ❌ {name}\n{(r.stderr or '')[-1800:]}"); raise SystemExit(1)
    print(f"  ✅ {name}")

for i, s in enumerate(timeline, 1):
    out = SHOTS / f"{str(i).zfill(2)}-{s['id']}.mp4"
    if out.exists() and out.stat().st_size > 50000: print(f"  ⏭ {out.name}"); continue
    frames = max(1, int(s["dur"]*FPS))
    vf = ("scale=2112:1188,"
          f"zoompan=z='min(1+0.07*on/{frames},1.07)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
          f"d=1:s={W}x{H}:fps={FPS},format=yuv420p")
    af = f"adelay=120|120,apad,atrim=0:{s['dur']:.3f},asetpts=N/SR/TB"
    run([FF,"-y","-loop","1","-framerate",str(FPS),"-t",f"{s['dur']:.3f}","-i",s["image"],"-i",s["audio"],
         "-filter_complex",f"[0:v]{vf}[v];[1:a]{af}[a]","-map","[v]","-map","[a]",
         "-c:v","libx264","-preset","veryfast","-crf","20","-c:a","aac","-b:a","160k","-shortest",str(out)], f"渲染 {out.name}")

lst = OUT/"concat.txt"
lst.write_text("\n".join("file '"+ (SHOTS/(str(i).zfill(2)+"-"+s["id"]+".mp4")).as_posix() +"'" for i,s in enumerate(timeline,1)), encoding="utf-8")
run([FF,"-y","-f","concat","-safe","0","-i",str(lst),"-c","copy",str(OUT/"concat.mp4")], "拼接")

final = DEMO/"rendered"/"invoice-eval-demo-v0.3.0-norecording.mp4"; final.parent.mkdir(parents=True, exist_ok=True)
vf2 = ("ass=subs.ass:fontsdir=C\\:/Windows/Fonts,"
       f"fade=t=in:st=0:d=0.6,fade=t=out:st={max(0,t0-1.2):.2f}:d=1.2")
run([FF,"-y","-i","concat.mp4","-vf",vf2,"-af","loudnorm=I=-16:TP=-1.5:LRA=11",
     "-c:v","libx264","-preset","medium","-crf","20","-c:a","aac","-b:a","192k",
     "-movflags","+faststart",str(final.resolve())], "烧字幕 + 输出", cwd=str(OUT))
print(f"\n  🎬 {final}  {final.stat().st_size/1024/1024:.1f} MB / {t0:.1f}s")

