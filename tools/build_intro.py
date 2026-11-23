"""Kirish animatsiyasining CSS'ini yasaydi: static/intro/intro.css

Ishga tushirish:  python3 tools/build_intro.py
Vaqt shkalasi T soniya. Har bir element o'z keyframes'iga ega, hammasi bitta
umumiy vaqt chizig'ida (0 dan T gacha) yuradi. Qisqa variant shu chiziqning
oxirgi qismini ko'rsatadi (index.html'da --d manfiy kechikish bilan).
"""
import math
import os

T = 9.2
EI = "cubic-bezier(.55,0,.9,.45)"   # tezlashib tushish
EO = "cubic-bezier(.2,.8,.2,1)"     # yumshoq to'xtash


def kf(name, pts):
    pts = sorted(pts, key=lambda p: p[0])
    if pts[0][0] > 0:
        pts = [(0,) + tuple(pts[0][1:])] + pts
    if pts[-1][0] < T:
        pts = pts + [(T,) + tuple(pts[-1][1:])]
    out = []
    for p in pts:
        body = p[1] + (";animation-timing-function:%s" % p[2] if len(p) > 2 else "")
        out.append("%.3f%%{%s}" % (p[0] / T * 100, body))
    return "@keyframes %s{%s}" % (name, "".join(out))


def anim(cls, name):
    return ".%s{animation:%s %ss linear var(--d,0s) 1 both}" % (cls, name, T)


K = []
# 1-sahna: chiziq -> MacBook yon tomondan burilib ochiladi
K.append(kf("xkLine", [(0, "opacity:1;transform:scaleX(0)", EO), (0.4, "opacity:1;transform:scaleX(1)"),
                       (0.55, "opacity:1;transform:scaleX(1)"), (0.85, "opacity:0;transform:scaleX(1.05)")]))
K.append(kf("xkCam", [(0, "opacity:0;transform:rotateY(-80deg)"), (0.4, "opacity:0;transform:rotateY(-80deg)"),
                      (0.6, "opacity:1;transform:rotateY(-80deg)", "cubic-bezier(.45,0,.2,1)"),
                      (2.1, "opacity:1;transform:rotateY(0deg)")]))
K.append(kf("xkLid", [(0, "transform:translateZ(-172px) rotateX(-90deg)"),
                      (0.75, "transform:translateZ(-172px) rotateX(-90deg)", "cubic-bezier(.5,0,.25,1)"),
                      (1.95, "transform:translateZ(-172px) rotateX(17deg)", EO),
                      (2.2, "transform:translateZ(-172px) rotateX(9deg)", EO),
                      (2.35, "transform:translateZ(-172px) rotateX(11deg)")]))
K.append(kf("xkZoom", [(0, "opacity:1;transform:scale(1)"), (3.72, "opacity:1;transform:scale(1)", EI),
                       (4.12, "opacity:0;transform:scale(4.4)"), (T - 0.01, "opacity:0;transform:scale(4.4)")]))
# ekran: eski televizordek yonish, shovqin, nuqtaga yig'ilib o'chish
K.append(kf("xkCrt", [(0, "opacity:0;transform:scaleY(.01)"), (2.2, "opacity:0;transform:scaleY(.01)"),
                      (2.24, "opacity:1;transform:scaleY(.01)", EO), (2.4, "opacity:1;transform:scaleY(1)"),
                      (2.6, "opacity:0;transform:scaleY(1)")]))
K.append(kf("xkStatic", [(0, "opacity:0;transform:scale(1,1)"), (2.38, "opacity:0;transform:scale(1,1)"),
                         (2.5, "opacity:1;transform:scale(1,1)"), (3.55, "opacity:1;transform:scale(1,1)", EI),
                         (3.74, "opacity:1;transform:scale(1,.012);filter:brightness(3)", EI),
                         (3.9, "opacity:1;transform:scale(0,.012);filter:brightness(3)"),
                         (3.92, "opacity:0;transform:scale(0,.012)")]))
K.append(kf("xkCdot", [(0, "opacity:0;transform:scale(.2)"), (3.8, "opacity:0;transform:scale(.2)"),
                       (3.88, "opacity:1;transform:scale(1)"), (4.1, "opacity:0;transform:scale(.3)")]))
# 2-sahna: magic harflari birma-bir
LETTERS = [("m", 4.35, (30, 47)), ("a", 4.5, (75, 47)), ("g", 4.65, (109, 57)),
           ("i", 4.8, (141, 47)), ("c", 4.95, (170, 47)), ("p", 5.2, (234, 51))]
for k, s, _ in LETTERS:
    hid = "opacity:0;transform:scale(.35) rotate(-14deg);filter:blur(10px)"
    on = "opacity:1;transform:scale(1) rotate(0deg);filter:blur(0)"
    K.append(kf("xkL" + k, [(0, hid), (s, hid, EO),
                            (s + 0.32, "opacity:1;transform:scale(1.12) rotate(3deg);filter:blur(0)"),
                            (s + 0.5, on), (8.4, on), (8.85, on.replace("opacity:1", "opacity:0"))]))
    K.append(kf("xkS" + k, [(0, "opacity:0;transform:scale(0) rotate(0deg)"),
                            (s + 0.12, "opacity:0;transform:scale(0) rotate(0deg)"),
                            (s + 0.3, "opacity:1;transform:scale(1) rotate(90deg)"),
                            (s + 0.56, "opacity:0;transform:scale(0) rotate(180deg)")]))
K.append(kf("xkGlow", [(0, "opacity:0;transform:scale(.7)"), (4.3, "opacity:0;transform:scale(.7)"),
                       (5.5, "opacity:.85;transform:scale(1)"), (7.05, "opacity:.85;transform:scale(1)"),
                       (7.3, "opacity:1;transform:scale(1.25)"), (7.9, "opacity:.85;transform:scale(1)"),
                       (8.4, "opacity:.85;transform:scale(1)"), (8.85, "opacity:0;transform:scale(1)")]))
# 3-sahna: tepadan UZMACBOOK tushadi, oxirgi "O" i harfining nuqtasiga aylanadi
for j, k in enumerate([0, 1, 2, 3, 4, 5, 7, 8]):
    s = 5.75 + 0.07 * j
    K.append(kf("xkR%d" % k, [(0, "opacity:0;transform:translateY(-560px)"),
                              (s, "opacity:0;transform:translateY(-560px)", EI),
                              (s + 0.06, "opacity:1;transform:translateY(-500px)", EI),
                              (s + 0.42, "opacity:1;transform:translateY(0)", EO),
                              (s + 0.52, "opacity:1;transform:translateY(-9px)", EI),
                              (s + 0.62, "opacity:1;transform:translateY(0)"),
                              (8.4, "opacity:1;transform:translateY(0)"), (8.85, "opacity:0;transform:translateY(0)")]))
K.append(kf("xkR6", [(0, "opacity:0;transform:translateY(-640px)"), (6.45, "opacity:0;transform:translateY(-640px)", EI),
                     (6.5, "opacity:1;transform:translateY(-590px)", EI),
                     (6.95, "opacity:1;transform:translateY(0) scale(1,1)", EO),
                     (7.01, "opacity:1;transform:translateY(3px) scale(1.18,.78)", EO),
                     (7.09, "opacity:1;transform:translateY(0) scale(1,1)", EO),
                     (7.3, "opacity:0;transform:translateY(0) scale(1.5,1.5)")]))
K.append(kf("xkDot", [(0, "opacity:0;transform:scale(.3) rotate(-90deg)"),
                      (7.06, "opacity:0;transform:scale(.3) rotate(-90deg)", EO),
                      (7.24, "opacity:1;transform:scale(1.2) rotate(12deg)", EO),
                      (7.4, "opacity:1;transform:scale(1) rotate(0deg)"), (8.4, "opacity:1;transform:scale(1) rotate(0deg)"),
                      (8.85, "opacity:0;transform:scale(1) rotate(0deg)")]))
K.append(kf("xkRing", [(0, "opacity:0;transform:scale(.4)"), (7.08, "opacity:0;transform:scale(.4)"),
                       (7.1, "opacity:1;transform:scale(.4)", EO), (7.62, "opacity:0;transform:scale(2.8)")]))
for n in range(8):
    a = math.radians(n * 45 + 22)
    K.append(kf("xkP%d" % n, [(0, "opacity:0;transform:translate(0,0) scale(1)"),
                              (7.1, "opacity:0;transform:translate(0,0) scale(1)"),
                              (7.12, "opacity:1;transform:translate(0,0) scale(1)", EO),
                              (7.75, "opacity:0;transform:translate(%.1fpx,%.1fpx) scale(.4)"
                               % (math.cos(a) * 62, math.sin(a) * 62))]))
K.append(kf("xkShine", [(0, "background-position:180% 0"),
                        (7.6, "background-position:180% 0", "cubic-bezier(.45,0,.3,1)"),
                        (8.3, "background-position:-80% 0")]))
K.append(kf("xkOver", [(0, "opacity:1"), (8.5, "opacity:1"), (T, "opacity:0")]))

A = [anim("xline", "xkLine"), anim("xcam", "xkCam"), anim("xlid", "xkLid"), anim("xzoom", "xkZoom"),
     anim("xcrt", "xkCrt"), anim("xstatic", "xkStatic"), anim("xcdot", "xkCdot"), anim("xglow", "xkGlow"),
     anim("xring", "xkRing"), anim("xdot", "xkDot"), anim("xshine", "xkShine"), anim("xin", "xkOver")]
A += [anim("xpc-" + k, "xkL" + k) for k, _, _ in LETTERS] + [anim("xsp-" + k, "xkS" + k) for k, _, _ in LETTERS]
A += [anim("xr%d" % k, "xkR%d" % k) for k in range(9)] + [anim("xpt%d" % n, "xkP%d" % n) for n in range(8)]

POLY = {"m": [(0, 0), (138, 0), (138, 234), (0, 234)],
        "a": [(138, 0), (205, 0), (205, 165), (175, 165), (175, 234), (138, 234)],
        "g": [(205, 0), (300, 0), (300, 165), (335, 165), (335, 234), (175, 234), (175, 165), (205, 165)],
        "i": [(300, 0), (345, 0), (345, 234), (335, 234), (335, 165), (300, 165)],
        "c": [(345, 0), (432, 0), (432, 234), (345, 234)],
        "p": [(432, 0), (640, 0), (640, 234), (432, 234)]}
SPARK = {"m": (24, 14), "a": (80, 16), "g": (118, 14), "i": (152, 22), "c": (182, 14), "p": (262, 24)}
PIECES = []
for k, _, (ox, oy) in LETTERS:
    cp = ", ".join("%.2f%% %.2f%%" % (x / 640 * 100, y / 234 * 100) for x, y in POLY[k])
    PIECES.append(".xpc-%s{clip-path:polygon(%s);transform-origin:%dpx %dpx}" % (k, cp, ox, oy))
    PIECES.append(".xsp-%s{left:%dpx;top:%dpx}" % ((k,) + SPARK[k]))
for k in range(9):
    PIECES.append(".xr%d{left:%.1fpx}" % (k, -47.6 + 30 * k))

BASE = """/* Avtomatik yasalgan: tools/build_intro.py — qo'lda o'zgartirmang */
.xin{position:fixed;inset:0;z-index:100;background:#000;display:flex;align-items:center;justify-content:center;overflow:hidden;cursor:pointer}
.xin.out{transition:opacity .25s;opacity:0 !important}
.xst{position:relative;width:390px;height:844px;flex:none;transform:scale(var(--s,1))}
.xst *{box-sizing:border-box}
.xzoom{position:absolute;inset:0;transform-origin:195px 352px}
.xline{position:absolute;left:85px;top:466px;width:220px;height:2px;border-radius:1px;background:#fff;box-shadow:0 0 12px rgba(255,255,255,.9),0 0 32px rgba(255,255,255,.45)}
.xpersp{position:absolute;left:30px;top:250px;width:330px;height:240px;perspective:900px;perspective-origin:50% 20%}
.xcam{position:absolute;inset:0;transform-style:preserve-3d;transform-origin:165px 222px}
.xdeck{position:absolute;left:0;top:222px;width:330px;height:172px;transform-origin:50% 0;transform:rotateX(-90deg);border-radius:0 0 10px 10px;background:linear-gradient(180deg,#3a3a3e,#2a2a2d)}
.xkb{position:absolute;left:11%;right:11%;top:9%;height:44%;border-radius:4px;background-color:#0c0c0e;background-image:repeating-linear-gradient(90deg,rgba(255,255,255,.07) 0 1px,transparent 1px 7.1%),repeating-linear-gradient(180deg,rgba(255,255,255,.07) 0 1px,transparent 1px 16.6%)}
.xtp{position:absolute;left:31%;right:31%;top:60%;height:32%;border-radius:6px;background:#323236;border:1px solid rgba(255,255,255,.08)}
.xfront{position:absolute;left:0;top:222px;width:330px;height:10.5px;display:block}
.xlid{position:absolute;left:0;top:0;width:330px;height:223px;transform-origin:50% 100%;transform-style:preserve-3d}
.xlidf{position:absolute;inset:0;width:330px;height:223px;display:block;backface-visibility:hidden;-webkit-backface-visibility:hidden}
.xlidb{position:absolute;inset:0;border-radius:12px 12px 2px 2px;background:linear-gradient(160deg,#55565b,#3b3c40 55%,#2c2d30);transform:rotateY(180deg);backface-visibility:hidden;-webkit-backface-visibility:hidden}
.xscr{position:absolute;left:3.05%;right:2.95%;top:7.09%;bottom:5.88%;overflow:hidden;background:#000;backface-visibility:hidden;-webkit-backface-visibility:hidden}
.xcrt{position:absolute;inset:0;background:#fff;box-shadow:0 0 30px #fff}
.xstatic{position:absolute;inset:0;background:#000;transform-origin:50% 50%}
.xnz{position:absolute;inset:-20%;background-image:url(noise.png);background-size:96px 96px;opacity:.9;animation:xjit .32s steps(1) infinite}
.xnz2{position:absolute;inset:-20%;background-image:url(noise.png);background-size:150px 150px;mix-blend-mode:difference;opacity:.55;animation:xjit2 .26s steps(1) infinite}
.xscan{position:absolute;inset:0;background:repeating-linear-gradient(180deg,rgba(0,0,0,.45) 0 1px,rgba(0,0,0,0) 1px 3px)}
.xroll{position:absolute;left:0;right:0;height:26%;background:linear-gradient(180deg,rgba(255,255,255,0),rgba(255,255,255,.22),rgba(255,255,255,0));animation:xroll .9s linear infinite}
.xtear{position:absolute;left:-10%;right:-10%;background-image:url(noise.png);background-size:60px 60px;filter:contrast(1.6)}
.xt1{top:22%;height:7%;animation:xtear .7s steps(1) infinite}
.xt2{top:58%;height:4%;animation:xtear .5s steps(1) .2s infinite}
.xt3{top:76%;height:10%;animation:xtear .9s steps(1) .1s infinite;opacity:.7}
.xcdot{position:absolute;left:50%;top:50%;width:14px;height:14px;margin:-7px 0 0 -7px;border-radius:50%;background:#fff;box-shadow:0 0 18px 6px rgba(255,255,255,.9)}
@keyframes xjit{0%{background-position:0 0}25%{background-position:-37px 21px}50%{background-position:19px -43px}75%{background-position:-11px -7px}}
@keyframes xjit2{0%{background-position:0 0;opacity:.55}33%{background-position:51px 12px;opacity:.3}66%{background-position:-23px 44px;opacity:.6}}
@keyframes xroll{0%{top:-30%}100%{top:105%}}
@keyframes xtear{0%{transform:translateX(0);opacity:.8}20%{transform:translateX(-14px)}40%{transform:translateX(9px);opacity:.4}60%{transform:translateX(-4px)}80%{transform:translateX(18px);opacity:.9}}
.xlk{position:absolute;left:79px;top:370px;width:280px;height:102.4px}
.xglow{position:absolute;left:-70px;top:-120px;width:420px;height:340px;border-radius:50%;background:radial-gradient(closest-side,rgba(255,255,255,.14),rgba(255,255,255,0))}
.xpc{position:absolute;left:0;top:0;width:280px;height:102.4px;display:block}
.xspk{position:absolute;width:16px;height:16px;margin:-8px 0 0 -8px;color:#fff;filter:drop-shadow(0 0 6px rgba(255,255,255,.9))}
.xrl{position:absolute;top:-1px;width:30px;height:30px;line-height:30px;text-align:center;font-family:'Unbounded','Arial Black',system-ui,sans-serif;font-size:26px;font-weight:700;-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;color:#fff;background-image:linear-gradient(180deg,#fff 0%,#f4f4f7 44%,#9e9ea6 54%,#e6e6ec 80%,#fff 100%)}
.xdot{position:absolute;left:132.6px;top:0;width:29.75px;height:28.44px;display:block;transform-origin:50% 50%}
.xring{position:absolute;left:130.4px;top:-3px;width:34px;height:34px;border-radius:50%;border:2px solid #fff}
.xpt{position:absolute;left:145.9px;top:12.5px;width:3px;height:3px;border-radius:50%;background:#fff;box-shadow:0 0 6px #fff}
.xshine{position:absolute;left:0;top:0;width:280px;height:102.4px;-webkit-mask-image:url(logo-nodot.png);mask-image:url(logo-nodot.png);-webkit-mask-size:100% 100%;mask-size:100% 100%;background-image:linear-gradient(105deg,rgba(255,255,255,0) 42%,rgba(255,255,255,.9) 50%,rgba(255,255,255,0) 58%);background-size:250% 100%;background-repeat:no-repeat}
.xskip{position:absolute;right:16px;bottom:calc(18px + env(safe-area-inset-bottom));font:600 13px/1 Inter,system-ui,sans-serif;color:rgba(255,255,255,.55);letter-spacing:.02em}
"""

out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "intro", "intro.css")
with open(out, "w", encoding="utf-8") as f:
    f.write(BASE + "\n".join(K) + "\n" + "\n".join(A) + "\n" + "\n".join(PIECES) + "\n")
print("yozildi:", out, os.path.getsize(out), "bayt")
