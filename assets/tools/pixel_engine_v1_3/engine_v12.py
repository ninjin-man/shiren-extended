#!/usr/bin/env python3
"""Generic, deterministic two-stage sprite pixelizer (no character-specific coordinates).

Python engine v1.2.  Inputs: RGB/RGBA character art with a visually separable subject.
Outputs: transparent precision master, transparent game sprite, diagnostics.
No generative AI, fixed face templates, manual color/hue classifications or hard-coded feature XYs.
Requires Pillow, NumPy, OpenCV.  python engine.py input.png --config config.json --output output_dir
"""
from __future__ import annotations
import argparse
import json
import hashlib
from pathlib import Path
from typing import Any
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

DEFAULTS: dict[str,Any] = {
    "background": "auto",  # auto|flat|grabcut|alpha
    "max_master_side": 104,
    "min_master_side": 68,
    "max_game_side": 64,
    "master_colors": 30,
    "game_colors": 22,
    "alpha_threshold": 0.47,
    "padding": 1,
    "max_source_side": 1600,
    "game_sampling": "nearest",  # retains master pixel clusters
    "spatial_strength": 2.8,  # neighbor color consistency (0 disables)
    "source_denoise": 30,  # bilateral color sigma at target resolution
    "min_region_pixels": 2,  # remove tiny near-color islands, not distinctive details
}


def bg_distance(rgb):
    """Perceptual distance from a border sample in 8-bit Lab units."""
    h,w=rgb.shape[:2]
    b=max(4,min(h,w)//32)
    border=np.concatenate((rgb[:b,:,:].reshape(-1,3),rgb[-b:,:,:].reshape(-1,3),
                            rgb[:, :b,:].reshape(-1,3),rgb[:,-b:,:].reshape(-1,3)),axis=0)
    border_l=cv2.cvtColor(border.reshape(-1,1,3),cv2.COLOR_RGB2LAB).reshape(-1,3)
    bg=np.median(border_l.astype(np.float32),axis=0)
    spread=np.median(np.linalg.norm(border_l.astype(np.float32)-bg,axis=1))
    lab=cv2.cvtColor(rgb,cv2.COLOR_RGB2LAB).astype(np.float32)
    d=np.linalg.norm(lab-bg,axis=2)
    return d,float(spread)


def largest_component(mask, min_area=10):
    n, lab, stats, _=cv2.connectedComponentsWithStats(mask.astype('uint8'),8)
    if n<=1:return np.zeros(mask.shape,bool)
    area=stats[1:,cv2.CC_STAT_AREA]
    label=1+int(np.argmax(area))
    if stats[label,cv2.CC_STAT_AREA]<min_area:return np.zeros(mask.shape,bool)
    return lab==label


def fill_holes(m):
    # flood from outside on inverse to fill enclosed light details (white dress, eyes)
    inp=m.astype('uint8')
    H,W=inp.shape
    inv=1-inp
    flood=inv.copy()
    cv2.floodFill(flood,np.zeros((H+2,W+2),np.uint8),(0,0),2)
    holes=(inv>0)&(flood!=2)
    return m|holes


def flat_background_mask(rgb, tolerance=18):
    dist,_=bg_distance(rgb)
    # Contrast seed, suppress faint JPEG halos.  This is not a material-specific rule.
    seed=(dist>tolerance).astype('uint8')
    seed=cv2.morphologyEx(seed,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
    main=largest_component(seed)
    if main.sum()==0:raise ValueError('Foreground not isolated in flat mode')
    main=fill_holes(main)
    # keep small extensions attached to main area but not disconnected background speckles
    near=cv2.dilate(main.astype('uint8'),np.ones((3,3),np.uint8))>0
    main=largest_component((main|((dist>tolerance*.65)&near)).astype('uint8'))
    return fill_holes(main), {'background_mode':'flat','border_distance_threshold':tolerance}


def grabcut_background_mask(rgb):
    H,W=rgb.shape[:2]
    # GrabCut is seeded with generic border and central-region assumptions only.
    # The border is guaranteed background.  High novelty central colors are foreground seeds.
    dist,bgspread=bg_distance(rgb)
    p=np.percentile(dist,90)
    gy,gx=np.mgrid[0:H,0:W]
    margin=max(4,int(min(H,W)*0.035))
    center=(gx>W*.12)&(gx<W*.88)&(gy>H*.12)&(gy<H*.88)
    probable=(dist>max(18,bgspread*1.8))
    surefg=(dist>max(27,float(p)*.57))&center
    surefg=cv2.morphologyEx(surefg.astype('uint8'),cv2.MORPH_OPEN,np.ones((3,3),np.uint8)).astype(bool)
    if int(surefg.sum())<75:
        surefg=(dist>np.percentile(dist,78))&center
    mask=np.where(probable,cv2.GC_PR_FGD,cv2.GC_PR_BGD).astype('uint8')
    mask[surefg]=cv2.GC_FGD
    mask[:margin,:]=cv2.GC_BGD
    mask[-margin:,:]=cv2.GC_BGD
    mask[:,:margin]=cv2.GC_BGD
    mask[:,-margin:]=cv2.GC_BGD
    # At least one sure BG, FG required.
    if int((mask==cv2.GC_FGD).sum())<50:
        raise ValueError('Background could not be separated automatically')
    bgmodel=np.zeros((1,65),dtype=np.float64);fgmodel=np.zeros((1,65),dtype=np.float64)
    cv2.setRNGSeed(12345)
    cv2.grabCut(cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR),mask,None,bgmodel,fgmodel,4,cv2.GC_INIT_WITH_MASK)
    raw=(mask==cv2.GC_FGD)|(mask==cv2.GC_PR_FGD)
    n,labels,stats,cents=cv2.connectedComponentsWithStats(raw.astype('uint8'),8)
    if n<=1:raise ValueError('No subject from GrabCut')
    # Object fragments (e.g. slime droplets) may be distinct, so keep substantial
    # components near the central cluster rather than all disconnected noise.
    size=int(raw.size)
    areas=stats[1:,cv2.CC_STAT_AREA]
    large=1+int(np.argmax(areas)); cx,cy=cents[large]
    keep=np.zeros_like(raw)
    for i in range(1,n):
        a=stats[i,cv2.CC_STAT_AREA]
        d=np.hypot((cents[i][0]-cx)/W,(cents[i][1]-cy)/H)
        if i==large or (a>=max(12,size*.000055) and d<.55):
            keep|=(labels==i)
    # Don't fill holes: transparent slime holes could be intentional (open rings).
    return keep,{'background_mode':'grabcut','border_spread':round(bgspread,2),
                 'foreground_components_kept':int(np.unique(labels[keep]).size)}


def isolate(src, cfg):
    if max(src.size)>cfg['max_source_side']:
        s=cfg['max_source_side']/max(src.size)
        src=src.resize((max(1,round(src.width*s)),max(1,round(src.height*s))),Image.Resampling.LANCZOS)
    rgba=np.asarray(src.convert('RGBA'))
    rgb=np.ascontiguousarray(rgba[:,:,:3])
    existing_a=rgba[:,:,3]
    mode=cfg['background']
    config_auto=(mode=='auto')
    auto_reason=None
    if mode=='auto':
        if np.count_nonzero(existing_a<254)>.05*existing_a.size:
            mode='alpha'
        else:
            _,spread=bg_distance(rgb)
            mode='flat' if spread<11 else 'grabcut'
    if mode=='alpha':
        mask=existing_a>=100
        diag={'background_mode':'alpha'}
    elif mode=='flat':
        mask,diag=flat_background_mask(rgb)
        # A supposedly flat-background segmentation that includes the outer
        # corners and ~all of the canvas has probably mistaken an off-white
        # second background tone for the subject. This catches multi-tone
        # neutral backgrounds, not particular characters or absolute XYs.
        H,W=mask.shape
        patch=max(2,round(min(H,W)*.04))
        corners=[mask[:patch,:patch],mask[:patch,-patch:],
                 mask[-patch:,:patch],mask[-patch:,-patch:]]
        corner_coverage=float(np.mean([p.mean() for p in corners]))
        if config_auto and float(mask.mean())>.80 and corner_coverage>.40:
            try:
                alt,alt_diag=grabcut_background_mask(rgb)
                if alt.sum()>=max(80,mask.sum()*.25):
                    mask=alt
                    diag=alt_diag
                    auto_reason='flat_background_corners_contaminated'
            except (cv2.error,ValueError):
                auto_reason='grabcut_attempt_failed_kept_flat'
    elif mode=='grabcut':
        mask,diag=grabcut_background_mask(rgb)
    else:raise ValueError('Unknown background method '+str(mode))
    if auto_reason:
        diag['auto_background_selection']=auto_reason
    yy,xx=np.where(mask)
    if len(xx)<80:raise ValueError('Could not extract a useful subject')
    bbox=(int(xx.min()),int(yy.min()),int(xx.max()+1),int(yy.max()+1))
    x0,y0,x1,y1=bbox
    crop=rgb[y0:y1,x0:x1].copy()
    alpha=mask[y0:y1,x0:x1].astype(np.uint8)
    result=np.dstack((crop,alpha*255))
    diag.update({'crop_bbox':list(bbox),'crop_size':[int(x1-x0),int(y1-y0)],
                 'foreground_fraction':round(float(mask.mean()),4)})
    return Image.fromarray(result,'RGBA'),diag


def choose_sizes(src,cfg):
    """Default: master max-side 68/88/104 by complexity; game 64 max-side.

    The pixel budget is only a heuristic, not a learned visual-quality metric.
    Both stages retain original aspect ratio; no fixed character 2D coords.
    """
    ar=np.asarray(src.convert('RGBA'))
    alpha=ar[:,:,3]>0
    rgb=ar[:,:,:3]
    # Detail density at a reference resolution, invariant-ish to source dimensions.
    ref_side=128
    w0,h0=src.size
    wref=round(w0*ref_side/max(w0,h0)); href=round(h0*ref_side/max(w0,h0))
    small=np.asarray(src.resize((wref,href),Image.Resampling.BILINEAR).convert('RGB'))
    gray=cv2.cvtColor(small,cv2.COLOR_RGB2GRAY)
    edges=cv2.Canny(gray,60,135)
    edge_density=float((edges>0).mean())
    if edge_density>.17: side=cfg['max_master_side']
    elif edge_density>.095: side=min(cfg['max_master_side'],88)
    else:side=min(cfg['max_master_side'],72)
    side=max(cfg['min_master_side'],side)
    master=(max(8,round(w0*side/max(w0,h0))),max(8,round(h0*side/max(w0,h0))))
    game_side=min(cfg['max_game_side'],max(master))
    game=(max(8,round(w0*game_side/max(w0,h0))),max(8,round(h0*game_side/max(w0,h0))))
    return master,game,round(edge_density,3)



def coherent_palette(rgb, fg, colors, spatial_strength=2.8, source_denoise=30, min_region_pixels=2):
    """Image-agnostic region-coherent palette, no part/character landmarks.

    1. Bilateral filtering averages similar colors but preserves strong contours.
    2. Compact palette is learned from foreground pixels only (no dithering).
    3. Iterated label optimization suppresses speckled color switches in areas
       with similar source colors, while protecting high-contrast boundaries.
    4. Tiny isolated same-color components are replaced only if surrounding
       colors are close to the original; eye highlights/stripes can survive.
    """
    H,W=fg.shape
    if not fg.any():raise ValueError('Empty foreground')
    # Use a neutral subject-color fill beyond the alpha mask for bilateral input.
    # For edge pixels, use a nearest-foreground RGB value so transparent black
    # does not pull outlines towards black.
    work=rgb.copy()
    if (~fg).any():
        from scipy.ndimage import distance_transform_edt
        iy,ix=distance_transform_edt(~fg,return_distances=False,return_indices=True)
        work[~fg]=work[iy[~fg],ix[~fg]]
    smoothed=cv2.bilateralFilter(work,5,float(source_denoise),1.25) if source_denoise else work
    # PIL median-cut: no dithering; internal palette selected on foreground only.
    prepared=smoothed.copy()
    prepared[~fg]=np.median(smoothed[fg].astype(np.float32),axis=0).astype(np.uint8)
    quant=Image.fromarray(prepared,'RGB').quantize(colors=int(colors),method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE).convert('RGB')
    q=np.asarray(quant)
    unique=np.unique(q[fg].reshape(-1,3),axis=0)
    if len(unique)==1:return np.where(fg[:,:,None],unique[0],0).astype('uint8')
    pal_lab=cv2.cvtColor(unique.reshape(-1,1,3),cv2.COLOR_RGB2LAB).reshape(-1,3).astype(np.float32)
    src_lab=cv2.cvtColor(smoothed,cv2.COLOR_RGB2LAB).astype(np.float32)
    # D(i,k) is unary penalty for assigning palette entry k to pixel i.
    # Penalize color shifts enough to preserve salient eye/flower accent colors.
    delta=src_lab[:,:,None,:]-pal_lab[None,None,:,:]
    unary=(delta*delta).sum(axis=3) # Lab 8-bit, squared distance
    lab_q=cv2.cvtColor(q,cv2.COLOR_RGB2LAB)
    # initialize label assignments from observed quantized colors
    index={tuple(map(int,c)):i for i,c in enumerate(unique)}
    labels=np.zeros((H,W),np.int16)
    for c,i in index.items():labels[np.all(q==c,axis=2)&fg]=i
    if spatial_strength>0:
        # Four-connected Potts regularizer, modulated by original edge strength.
        # A local color jump is evidence of a true material boundary.
        lam=float(spatial_strength)*24.
        for _ in range(4):
            energy=unary.copy()
            for dy,dx in ((-1,0),(1,0),(0,-1),(0,1)):
                neighbor=np.roll(labels,(dy,dx),axis=(0,1))
                valid=np.roll(fg,(dy,dx),axis=(0,1))&fg
                if dy<0: valid[-1,:]=False
                if dy>0: valid[0,:]=False
                if dx<0: valid[:,-1]=False
                if dx>0: valid[:,0]=False
                neighbor_lab=np.roll(src_lab,(dy,dx),axis=(0,1))
                edge=np.linalg.norm(src_lab-neighbor_lab,axis=2)
                weight=(lam*np.exp(-((edge/27.0)**2))).astype(np.float32)*valid
                energy+=weight[:,:,None]*(np.arange(len(unique),dtype=np.int16)[None,None,:]!=neighbor[:,:,None])
            labels[fg]=np.argmin(energy,axis=2)[fg]
    if min_region_pixels>0:
        # Only remove regions no larger than N pixels when all neighbors support
        # an alternate close color. Strong contrast features stay untouched.
        for idx in range(len(unique)):
            mask=(labels==idx)&fg
            if not mask.any():continue
            n,components,stats,_=cv2.connectedComponentsWithStats(mask.astype('uint8'),4)
            for cc in range(1,n):
                if int(stats[cc,cv2.CC_STAT_AREA])>int(min_region_pixels):continue
                ys,xs=np.where(components==cc)
                support={}
                for y,x in zip(ys,xs):
                    for ny,nx in ((y-1,x),(y+1,x),(y,x-1),(y,x+1)):
                        if 0<=ny<H and 0<=nx<W and fg[ny,nx] and components[ny,nx]!=cc:
                            k=int(labels[ny,nx]);support[k]=support.get(k,0)+1
                if not support:continue
                other=max(support,key=lambda k:(support[k],-k))
                # Do not remove meaningful high-contrast small marks.
                target=pal_lab[other]
                orig=src_lab[ys,xs]
                dist=np.linalg.norm(orig-target,axis=1)
                if float(dist.mean())<19 and other!=idx:
                    labels[ys,xs]=other
    out=unique[labels]
    out[~fg]=0
    return out.astype('uint8')


def convert(src: Image.Image,size,colors,alpha_threshold,padding=0,spatial_strength=2.8,source_denoise=30,min_region_pixels=2):
    """Coverage-normalized downsampling with region-coherent LAB palette."""
    rgb=np.asarray(src.convert('RGB')).astype(np.float32)
    a=np.asarray(src.getchannel('A')).astype(np.float32)/255.0
    tw,th=size
    xoff=yoff=0
    if padding>0:
        scale=min((tw-2*padding)/src.width,(th-2*padding)/src.height)
        dw=max(1,round(src.width*scale));dh=max(1,round(src.height*scale))
        xoff=(tw-dw)//2;yoff=(th-dh)//2
    else:dw,dh=tw,th
    coverage=cv2.resize(a,(dw,dh),interpolation=cv2.INTER_AREA)
    mass=cv2.resize(rgb*a[:,:,None],(dw,dh),interpolation=cv2.INTER_AREA)
    avg=np.rint(mass/np.maximum(coverage[:,:,None],.0001)).clip(0,255).astype('uint8')
    fg=coverage>=alpha_threshold
    if int(fg.sum())<50: raise ValueError('Result has too few opaque pixels')
    picked=coherent_palette(avg,fg,colors,spatial_strength,source_denoise,min_region_pixels)
    result=np.zeros((th,tw,4),np.uint8)
    dst=result[yoff:yoff+dh,xoff:xoff+dw]
    dst[:,:,:3]=picked
    dst[:,:,3]=fg.astype('uint8')*255
    return Image.fromarray(result,'RGBA')


def reduce_game(master: Image.Image, size, colors: int,sampling='nearest',spatial_strength=2.8,source_denoise=30,min_region_pixels=2):
    """Game image is strictly a reduced master, with a second generic coherence pass."""
    mode=Image.Resampling.NEAREST if sampling=='nearest' else Image.Resampling.BOX
    reduced=master.resize(size,mode).convert('RGBA')
    rgba=np.asarray(reduced).copy()
    mask=rgba[:,:,3]>0
    rgb=coherent_palette(rgba[:,:,:3],mask,colors,spatial_strength,source_denoise,min_region_pixels)
    rgba[:,:,:3]=rgb
    rgba[:,:,3]=mask.astype('uint8')*255
    return Image.fromarray(rgba,'RGBA')


def rgba_stat(img):
    arr=np.asarray(img)
    opaque=arr[:,:,3]>0
    return {'size':list(img.size),'colors':int(len(np.unique(arr[opaque,:3],axis=0))),
            'opaque_pixels':int(opaque.sum()),'bytes_estimate_png':None}


def make_comparison(samples,output):
    """One portrait per-source row, 3 images per row, 1x and zoom on cards."""
    W=960;rowh=425
    H=72+rowh*len(samples)
    page=Image.new('RGB',(W,H),(14,25,36));d=ImageDraw.Draw(page)
    try:
        ft=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',23)
        small=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',17)
    except OSError:ft=small=ImageFont.load_default()
    d.text((20,15),'GENERIC ENGINE v1  |  same code, different source artwork',font=ft,fill=(236,244,240))
    for i,(name,src,mst,game,diag) in enumerate(samples):
        y=72+i*rowh
        d.text((22,y),str(i+1)+'. '+name[:33]+'   ['+diag['background_mode']+']',font=small,fill=(214,236,222))
        columns=[('Original',src),('Master %s'%('×'.join(map(str,mst.size))),mst),('Game %s'%('×'.join(map(str,game.size))),game)]
        for j,(label,im) in enumerate(columns):
            x=20+j*310
            d.text((x,y+27),label,font=small,fill=(233,237,229))
            bg=Image.new('RGB',(284,335),(41,53,64));dd=ImageDraw.Draw(bg)
            for cy in range(0,335,20):
                for cx in range(0,284,20):
                    if (cy//20+cx//20)%2==0:dd.rectangle((cx,cy,cx+19,cy+19),fill=(53,67,79))
            if j==0:
                t=im.copy(); t.thumbnail((265,300),Image.Resampling.LANCZOS)
            else:
                # zoom to nearest size fitting card; no interpolated pixels
                z=max(1,min(8,260//im.width,300//im.height))
                t=im.resize((im.width*z,im.height*z),Image.Resampling.NEAREST)
            bg.paste(t,((284-t.width)//2,(305-t.height)//2),t)
            page.paste(bg,(x,y+51))
            if j>0:
                # native 1x at card bottom
                native=Image.new('RGBA',(im.width,im.height),(41,53,64,255))
                native.alpha_composite(im)
                if native.width<=85 and native.height<=100:
                    page.paste(native.convert('RGB'),(x+190,y+283))
    page.save(output,optimize=True)


def run_one(source_path:Path, root:Path, config:dict, name:str):
    original=Image.open(source_path).convert('RGBA')
    fg,diag=isolate(original,config)
    # Automatic technical warning only. Front-facing / full-body anatomy
    # cannot be proven with color segmentation; manual approval still needed.
    original_alpha=np.asarray(original.convert('RGBA'))[:,:,3]
    if not (original_alpha<254).any():
        rgb=np.asarray(original.convert('RGB'))
        dist,_=bg_distance(rgb)
        border_touch=float((dist[-max(2,original.height//100):,:]>20).mean())
    else:
        border_touch=float((original_alpha[-max(2,original.height//100):,:]>127).mean())
    diag['input_lower_edge_subject_fraction']=round(border_touch,3)
    diag['framing_review_required']=bool(border_touch>0.08)
    diag['framing_note']='Ensure full-body, frontal pose, feet visible; anatomy not automatically verified.'
    master_size,game_size,edges=choose_sizes(fg,config)
    master=convert(fg,master_size,config['master_colors'],config['alpha_threshold'],config['padding'],config['spatial_strength'],config['source_denoise'],config['min_region_pixels'])
    # Pixel-only direct reduction of master for game, never a separate manual draw.
    game=reduce_game(master,game_size,config['game_colors'],config['game_sampling'],config['spatial_strength'],config['source_denoise'],config['min_region_pixels'])
    folder=root/name;folder.mkdir(parents=True,exist_ok=True)
    fg.save(folder/'isolated.png',optimize=True)
    master.save(folder/'master.png',optimize=True)
    game.save(folder/'game.png',optimize=True)
    # Reasonably sized nearest-neighbor zoom files even for large master.
    for filename,im in [('master_zoom.png',master),('game_zoom.png',game)]:
        z=max(2,min(8,900//max(im.size)))
        im.resize((im.width*z,im.height*z),Image.Resampling.NEAREST).save(folder/filename,optimize=True)
    diag.update({'source_name':source_path.name,'master':rgba_stat(master),'game':rgba_stat(game),
                 'edge_density':edges,'source_size':list(original.size)})
    for stage in ('master','game'):
        p=folder/(stage+'.png')
        diag[stage]['bytes_png']=p.stat().st_size
        diag[stage]['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
    (folder/'report.json').write_text(json.dumps(diag,ensure_ascii=False,indent=2),encoding='utf-8')
    return (name,fg,master,game,diag)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs',nargs='+',type=Path,help='one or more source images')
    parser.add_argument('--config',type=Path,default=Path(__file__).parent/'config.json')
    parser.add_argument('--output',type=Path,default=Path('output'))
    a=parser.parse_args()
    cfg=DEFAULTS.copy()
    if a.config.exists():cfg.update(json.loads(a.config.read_text(encoding='utf-8')))
    a.output.mkdir(parents=True,exist_ok=True)
    finished=[];failures=[]
    for i,p in enumerate(a.inputs):
        if not p.exists():failures.append({'file':str(p),'error':'not found'});continue
        try:
            print('Processing',p.name,flush=True)
            finished.append(run_one(p,a.output,cfg,f'input_{i+1}'))
        except (ValueError,cv2.error) as e:
            failures.append({'file':p.name,'error':str(e)})
    if finished:make_comparison(finished,a.output/'comparison.png')
    report={'engine_version':'1.2','config':cfg,'processed':len(finished),'failed':failures,
            'samples':[r[-1] for r in finished]}
    (a.output/'batch_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'processed':len(finished),'failed':failures,
          'size_pairs':[(s[2].size,s[3].size) for s in finished]},ensure_ascii=False,indent=2))
    if not finished:raise SystemExit(1)

if __name__=='__main__':main()