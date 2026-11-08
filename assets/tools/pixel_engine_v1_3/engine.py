#!/usr/bin/env python3
"""Generic game-readability pixelizer v1.3 — no character-specific coordinates.

Usage:
  python engine.py character1.png character2.png --config config.json --output output

Requirements: numpy, Pillow, opencv-python, scipy (the last is used by v1.2).
Results: source crop, precise master, v1.2 game baseline, v1.3 game,
optional v1.3 detail game and comparison, with per-character diagnostics.

The generic game stage protects high-contrast dark ink lines when shrinking.
No face rectangles, hard-coded palette, class ID, body landmarks or species logic.
This does NOT re-pose, re-draw or guarantee game-ready animation frames.
"""
from __future__ import annotations
import argparse,hashlib,json,math
from pathlib import Path
import numpy as np
import cv2
from PIL import Image,ImageDraw,ImageFont
from scipy.ndimage import distance_transform_edt
import engine_v12 as core

DEFAULT={
  'max_master_side':128,'min_master_side':68,'max_game_side':64,
  'detail_game_side':80,'master_colors':30,'game_colors':24,
  'alpha_threshold':.47,'ink_local_contrast':14.0,
  'ink_luminance_ceiling':170,'ink_area_threshold':.32,
  'spatial_strength':2.8,'source_denoise':30,'min_region_pixels':2,
  'game_spatial_strength':2.6,'game_source_denoise':18,'game_min_region_pixels':1,
  'background':'auto','padding':1,'max_source_side':1600,
  'game_sampling':'nearest'
}


def game_from_master(master:Image.Image,size:tuple[int,int],cfg:dict)->tuple[Image.Image,dict]:
    """Contrast-preserving game resampling with palette coherence.

    1. Source-alpha weighted area shrink, retaining shape (not nearest-only).
    2. Find source dark strokes by local contrast to neighbors, not by XY or hue.
    3. Where enough dark ink crosses the destination cell, sample that stroke
       rather than averaging it away. Below threshold, use area color.
    4. Spatially coherent palette reduction avoids color speckles.
    """
    src=np.array(master.convert('RGBA'),dtype=np.uint8)
    fg=src[:,:,3]>0
    if fg.sum()<50:raise ValueError('Insufficient foreground pixels')
    rgb=src[:,:,:3]
    work=rgb.copy()
    if (~fg).any():
        iy,ix=distance_transform_edt(~fg,return_distances=False,return_indices=True)
        work[~fg]=work[iy[~fg],ix[~fg]]
    gray=cv2.cvtColor(work,cv2.COLOR_RGB2GRAY).astype(np.float32)
    reference=cv2.GaussianBlur(gray,(5,5),1.05)
    ink=(fg & (reference-gray>float(cfg['ink_local_contrast'])) &
         (gray<float(cfg['ink_luminance_ceiling']))).astype(np.float32)
    w,h=size
    alpha=fg.astype(np.float32)
    coverage=cv2.resize(alpha,(w,h),interpolation=cv2.INTER_AREA)
    fg_small=coverage>=float(cfg['alpha_threshold'])
    area=cv2.resize(work.astype(np.float32)*alpha[:,:,None],(w,h),interpolation=cv2.INTER_AREA)
    area=np.rint(area/np.maximum(coverage[:,:,None],1e-5)).clip(0,255).astype(np.uint8)
    ink_cov=cv2.resize(ink,(w,h),interpolation=cv2.INTER_AREA)
    ink_mass=cv2.resize(work.astype(np.float32)*ink[:,:,None],(w,h),interpolation=cv2.INTER_AREA)
    ink_rgb=np.rint(ink_mass/np.maximum(ink_cov[:,:,None],1e-5)).clip(0,255).astype(np.uint8)
    # Preserve only robust strokes, not isolated single-source-pixel dark noise.
    protected=(ink_cov>=float(cfg['ink_area_threshold']))&fg_small
    area[protected]=ink_rgb[protected]
    result_rgb=core.coherent_palette(area,fg_small,int(cfg['game_colors']),
            spatial_strength=float(cfg['game_spatial_strength']),
            source_denoise=float(cfg['game_source_denoise']),
            min_region_pixels=int(cfg['game_min_region_pixels']))
    rgba=np.dstack((result_rgb,fg_small.astype(np.uint8)*255))
    return Image.fromarray(rgba,'RGBA'),{'stroke_pixels':int(protected.sum()),
                    'stroke_ratio':round(float(protected.sum()/max(int(fg_small.sum()),1)),3)}


def max_side_size(size,side):
    w,h=size;s=max(w,h)
    return max(1,round(w*side/s)),max(1,round(h*side/s))


def stats(im):
    a=np.asarray(im.convert('RGBA'))
    fg=a[:,:,3]>0
    colors=len(np.unique(a[fg,:3],axis=0))
    return {'size':list(im.size),'colors':int(colors),'pixels':int(fg.sum()),'alpha_values':list(map(int,np.unique(a[:,:,3])))}


def checker(w,h):
    bg=Image.new('RGB',(w,h),(39,52,62));d=ImageDraw.Draw(bg)
    for y in range(0,h,20):
        for x in range(0,w,20):
            if ((x//20+y//20)&1)==0:
                d.rectangle((x,y,min(w,x+20),min(h,y+20)),fill=(53,67,77))
    return bg


def fit_image(img,area,src=False):
    x0,y0,ww,hh=area
    if src:
        disp=img.copy();disp.thumbnail((ww-12,hh-12),Image.Resampling.LANCZOS)
    else:
        factor=max(1,min(5,(ww-12)//img.width,(hh-12)//img.height))
        disp=img.resize((factor*img.width,factor*img.height),Image.Resampling.NEAREST)
    x=x0+(ww-disp.width)//2;y=y0+(hh-disp.height)//2
    return disp,(x,y)


def comparison(items,output):
    W=1036;rh=358;H=76+rh*len(items)
    page=Image.new('RGB',(W,H),(17,27,37));d=ImageDraw.Draw(page)
    try:
        f=ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',19)
        fs=ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',15)
    except OSError:f=fs=ImageFont.load_default()
    d.text((18,13),'汎用ドット絵エンジン v1.3 ｜ 同一処理で4キャラ比較',font=f,fill='#e9f5ed')
    d.text((18,43),'原画　/　旧64px　/　改良64px　/　高精細80px',font=fs,fill='#bdd5c6')
    cats=['原画','旧ゲーム用','改良ゲーム用','高精細ゲーム用']
    for i,(name,source,old,new,detail,report) in enumerate(items):
        y=76+i*rh
        d.text((18,y+3),name,font=f,fill='#ffffff')
        for j,(label,im) in enumerate(zip(cats,[source,old,new,detail])):
            x=16+j*255;d.text((x,y+28),label,font=fs,fill='#d4e4d7')
            bg=checker(245,284)
            disp,pos=fit_image(im,(0,0,245,284),src=(j==0))
            if j==0:
                bg.paste(disp,pos,disp if disp.mode=='RGBA' else None)
            else:
                bg.paste(disp,pos,disp)
            page.paste(bg,(x,y+50))
            if j>=1:
                d.text((x+8,y+336),f'{im.width} x {im.height} px',font=fs,fill='#a8c5b4')
    page.save(output,optimize=True)


def run_one(path:Path,root:Path,name:str,cfg:dict,display_name:str|None=None):
    src=Image.open(path).convert('RGBA')
    fg,segdiag=core.isolate(src,cfg)
    msize,gsize,detail_density=core.choose_sizes(fg,cfg)
    master=core.convert(fg,msize,int(cfg['master_colors']),cfg['alpha_threshold'],cfg['padding'],
            cfg['spatial_strength'],cfg['source_denoise'],cfg['min_region_pixels'])
    oldcfg=core.DEFAULTS.copy();oldcfg.update(cfg)
    old_game=core.reduce_game(master,gsize,22,'nearest',2.8,30,2)
    new_game,ink64=game_from_master(master,gsize,cfg)
    detail_side=int(cfg['detail_game_side'])
    detailed,ink80=game_from_master(master,max_side_size(msize,detail_side),cfg)
    folder=root/name;folder.mkdir(parents=True,exist_ok=True)
    # Only save a compact source preview here; full originals are not duplicated.
    preview=fg.copy()
    preview.thumbnail((360,360),Image.Resampling.LANCZOS)
    preview.save(folder/'input_preview.png')
    for k,im in [('master',master),('before64',old_game),('game64',new_game),('game80',detailed)]:
        im.save(folder/(k+'.png'),optimize=True)
    result={'source_file':path.name,'label':display_name or path.stem,'segmentation':segdiag,
            'master':stats(master),'game_before':stats(old_game),
            'game64':stats(new_game),'game80':stats(detailed),
            'ink64':ink64,'ink80':ink80,'detail_density':detail_density,
            'original_width_height':list(src.size)}
    for k in ('master','before64','game64','game80'):
        b=(folder/(k+'.png')).read_bytes()
        result[k+'_sha256']=hashlib.sha256(b).hexdigest()
    (folder/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    return (result['label'],fg,old_game,new_game,detailed,result)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('inputs',type=Path,nargs='+')
    ap.add_argument('--output',type=Path,default=Path('output'))
    ap.add_argument('--labels',nargs='*',help='optional display names in input order')
    ap.add_argument('--config',type=Path,default=Path(__file__).parent/'config.json')
    a=ap.parse_args()
    if a.labels and len(a.labels)!=len(a.inputs):
        ap.error('--labels needs one label per input image')
    cfg=DEFAULT.copy()
    if a.config.is_file():cfg.update(json.loads(a.config.read_text(encoding='utf8')))
    a.output.mkdir(parents=True,exist_ok=True)
    results=[];fail=[]
    for i,input in enumerate(a.inputs):
        try:
            print('Converting',input.name,flush=True)
            display=(a.labels[i] if a.labels else (input.parent.name if input.stem=='original' else input.stem))
            results.append(run_one(input,a.output,f'input_{i+1}',cfg,display))
        except (OSError,ValueError,cv2.error) as err:
            fail.append({'source':input.name,'error':str(err)})
    if results:comparison(results,a.output/'comparison.png')
    report={'version':'1.3','settings':cfg,'processed':len(results),'failed':fail,
            'items':[i[-1] for i in results]}
    (a.output/'batch_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'converted':len(results),'failed':fail,
          'sizes':[(i[3].size,i[4].size) for i in results]},ensure_ascii=False,indent=2))
    if not results:raise SystemExit(1)

if __name__=='__main__':main()