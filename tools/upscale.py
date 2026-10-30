#!/usr/bin/env python3
"""4x upscale of painted art (storyboard sheets, small panels) with Real-ESRGAN general x4v3, CPU.

  python upscale.py realesr-general-x4v3.pth sheet.png sheet_x4.png

Weights (5 MB): GitHub xinntao/Real-ESRGAN release v0.2.5.0, realesr-general-x4v3.pth.
pip install torch (CPU build is enough). About 1 s per 256x256 tile on 2 cores; a 1672x941
sheet takes about a minute. Tiled with overlap, so any image size works.
"""
import sys, numpy as np, torch, torch.nn as nn, torch.nn.functional as F
from PIL import Image


class SRVGGNetCompact(nn.Module):
    def __init__(s, nin=3, nout=3, feat=64, nconv=32, up=4):
        super().__init__(); s.up = up
        b = [nn.Conv2d(nin, feat, 3, 1, 1), nn.PReLU(feat)]
        for _ in range(nconv): b += [nn.Conv2d(feat, feat, 3, 1, 1), nn.PReLU(feat)]
        b += [nn.Conv2d(feat, nout * up * up, 3, 1, 1)]
        s.body = nn.ModuleList(b); s.ps = nn.PixelShuffle(up)

    def forward(s, x):
        o = x
        for m in s.body: o = m(o)
        return s.ps(o) + F.interpolate(x, scale_factor=s.up, mode='nearest')


w, src, dst = sys.argv[1:4]
torch.set_num_threads(2)
net = SRVGGNetCompact(); sd = torch.load(w, map_location='cpu')
net.load_state_dict(sd.get('params', sd)); net.eval()
img = np.asarray(Image.open(src).convert('RGB'), np.float32) / 255
H, W, _ = img.shape; T, P, S = 256, 12, 4
out = np.zeros((H * S, W * S, 3), np.float32)
x = torch.from_numpy(img).permute(2, 0, 1)[None]
with torch.no_grad():
    for y0 in range(0, H, T):
        for x0 in range(0, W, T):
            ya, xa = max(0, y0 - P), max(0, x0 - P)
            yb, xb = min(H, y0 + T + P), min(W, x0 + T + P)
            r = net(x[:, :, ya:yb, xa:xb])[0].permute(1, 2, 0).numpy()
            ty, tx = min(T, H - y0), min(T, W - x0)
            oy, ox = (y0 - ya) * S, (x0 - xa) * S
            out[y0*S:(y0+ty)*S, x0*S:(x0+tx)*S] = r[oy:oy+ty*S, ox:ox+tx*S]
Image.fromarray((np.clip(out, 0, 1) * 255 + .5).astype(np.uint8)).save(dst)
print('wrote', dst, out.shape)
