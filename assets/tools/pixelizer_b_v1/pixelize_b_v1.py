#!/usr/bin/env python3
"""B route: faithful, feature-preserving pixel art from a concept illustration.

Required: pillow, numpy, opencv-python (cv2).
Examples:
    python pixelize_b_v1.py original.png --size 48x48 --bg black \
        --config pixelize_b_v1_config.json --out result.png
    python pixelize_b_v1.py elf.png --size 64x112 --bg white --out elf.png

Do not assume that the program understands semantic parts. A JSON region is a
user-supplied *hint*, not automated recognition. Pure Python/OpenCV/Pillow,
no generative AI and no need for Internet. Never copies copyrighted references.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
import cv2
from PIL import Image, ImageDraw


def parse_wh(s):
    try:
        w,h = map(int,s.lower().split('x'))
        if not 8<=w<=256 or not 8<=h<=256: raise ValueError()
        return w,h
    except Exception:
        raise argparse.ArgumentTypeError('size must be WIDTHxHEIGHT (8..256)')


def classify_fg(image: Image.Image, mode='auto', tolerance=26):
    """Classify background by border-connectivity, avoiding a simple green hue rule.

    Prefer genuine alpha for transparent assets. Otherwise use known black/white
    or average corner color. Flood-fill bg-like pixels from frame borders.
    This is a deterministic heuristic for plain backgrounds, not matting for
    detailed scenery or near-white hair touching white background.
    """
    rgb=np.array(image.convert('RGB'))
    a=np.array(image.convert('RGBA'))[:,:,3]
    h,w=rgb.shape[:2]
    if np.any(a<253):
        fg=(a>=32).astype(np.uint8)
        src_alpha=True
    else:
        src_alpha=False
        if mode=='black': ref=np.array([0,0,0])
        elif mode=='white': ref=np.array([255,255,255])
        else:
            z=max(2,min(12,min(w,h)//60))
            corners=np.concatenate([rgb[:z,:z].reshape(-1,3),rgb[:z,-z:].reshape(-1,3),rgb[-z:,:z].reshape(-1,3),rgb[-z:,-z:].reshape(-1,3)])
            ref=np.median(corners,axis=0)
        diff=np.max(np.abs(rgb.astype(np.int16)-ref.astype(np.int16)),axis=2)
        bg_candidate=(diff<=tolerance).astype(np.uint8)
        # background-like pixels only if connected to the border
        # padding creates an outside frame for flood fill, even if corners vary.
        padded=np.pad(bg_candidate,1,mode='constant',constant_values=1)
        ff=padded.copy()
        floodmask=np.zeros((h+4,w+4),np.uint8)
        cv2.floodFill(ff,floodmask,(0,0),2)
        connected=(ff[1:-1,1:-1]==2)
        fg=(~connected).astype(np.uint8)
        # Tiny near-edge background noise is not a sprite: keep meaningful blobs.
    n,l,stats,_=cv2.connectedComponentsWithStats(fg,8)
    if n>1:
        size=h*w
        min_area=max(8,int(size*0.000025))
        keep=np.zeros_like(fg)
        largest=int(np.max(stats[1:,cv2.CC_STAT_AREA]))
        for i in range(1,n):
            area=int(stats[i,cv2.CC_STAT_AREA])
            if area>=max(min_area,int(largest*.00025)):
                keep[l==i]=1
        fg=keep
    if not fg.any(): raise ValueError('foreground not detected; try --bg black, white, or a PNG with alpha')
    return rgb,fg,src_alpha


def lab_quantize(samples, k, rngseed=91):
    pts=samples.reshape(-1,1,3)
    lab=cv2.cvtColor(pts,cv2.COLOR_RGB2LAB).reshape(-1,3).astype(np.float32)
    k=min(k,len(lab),len(np.unique(lab,axis=0)))
    if k<1:return np.empty((0,3),dtype=np.uint8)
    cv2.setRNGSeed(rngseed)
    _, idx, centers=cv2.kmeans(lab,k,None,
        (cv2.TERM_CRITERIA_EPS+cv2.TERM_CRITERIA_MAX_ITER,50,.2),3,cv2.KMEANS_PP_CENTERS)
    colors=cv2.cvtColor(np.clip(np.rint(centers),0,255).astype(np.uint8).reshape(-1,1,3),cv2.COLOR_LAB2RGB).reshape(-1,3)
    return colors[idx.flatten()]


def area_color(crop,mask,width,height):
    a=mask.astype(np.float32)
    cov=cv2.resize(a,(width,height),interpolation=cv2.INTER_AREA)
    numerator=cv2.resize(crop.astype(np.float32)*a[:,:,None],(width,height),interpolation=cv2.INTER_AREA)
    color=np.uint8(np.clip(np.rint(numerator/np.maximum(.035,cov[:,:,None])),0,255))
    return color,cov


def get_roi(box,w,h):
    x0,y0,x1,y1=box
    return max(0,min(w,int(np.floor(x0*w)))),max(0,min(h,int(np.floor(y0*h)))),max(0,min(w,int(np.ceil(x1*w)))),max(0,min(h,int(np.ceil(y1*h))))


def detect_feature_hints(src_rgb,src_mask,feature,ow,oh):
    """A region is normalized to *cropped foreground bbox* (0..1)."""
    h,w=src_mask.shape
    x0,y0,x1,y1=get_roi(feature['box'],w,h)
    region=np.zeros((h,w),np.uint8)
    if x0>=x1 or y0>=y1:return None
    region[y0:y1,x0:x1]=255
    target=np.array(feature.get('target_rgb',[248,213,43]),dtype=np.uint8)
    tl=cv2.cvtColor(target.reshape(1,1,3),cv2.COLOR_RGB2LAB).astype(np.float32).reshape(3)
    sl=cv2.cvtColor(src_rgb,cv2.COLOR_RGB2LAB).astype(np.float32)
    delta=np.sqrt(np.sum(((sl-tl)[...])**2,axis=2))
    # Optional 'warm-yellow': prevents lime glare from being mistaken for yellow eyes.
    near=(delta<=feature.get('lab_distance',55))
    if feature.get('kind')=='warm-yellow':
        R=src_rgb[:,:,0].astype(np.float32)
        G=src_rgb[:,:,1].astype(np.float32)
        B=src_rgb[:,:,2].astype(np.float32)
        near&=(R>=.90*G)&(R>125)&(G>110)&(B<.70*G)
    if feature.get('kind')=='green':
        R=src_rgb[:,:,0].astype(np.float32)
        G=src_rgb[:,:,1].astype(np.float32)
        near&=(G>R*1.12)
    positive=near&(region>0)&(src_mask>0)
    if np.count_nonzero(positive)==0:return None
    cy,cx=np.median(np.argwhere(positive),axis=0)
    mask_small=cv2.resize(positive.astype(np.float32),(ow,oh),interpolation=cv2.INTER_AREA)
    return {'mask':mask_small,'center':(float(cx/w*ow),float(cy/h*oh)), 'rgb':target, 'min_pixels':int(feature.get('min_pixels',1)), 'max_pixels':int(feature.get('max_pixels',999)), 'name':feature.get('name','feature')}


def apply_features(dst,features,place_x,place_y,sw,sh):
    """Reserve at least one pixel of each declared eye and keep chosen eye hue.
    Only recolor inside the *existing silhouette*. Never create a disconnected eye.
    """
    report=[]
    for feature in features:
        cov=feature['mask']
        candidates=[(float(cov[y,x]),x,y) for y in range(sh) for x in range(sw)
                    if cov[y,x]>.03 and dst[place_y+y,place_x+x,3]>0]
        candidates.sort(reverse=True)
        selected=[(x,y) for score,x,y in candidates if score>=.22]
        minpx=feature['min_pixels']
        if len(selected)<minpx:
            selected=list(dict.fromkeys(selected+[(x,y) for _,x,y in candidates[:minpx]]))
        if selected:
            ranked=sorted(selected, key=lambda v:float(cov[v[1],v[0]]), reverse=True)
            selected=ranked[:feature['max_pixels']]
        if not selected:
            cx,cy=feature['center'];xs=range(max(0,int(cx)-2),min(sw,int(cx)+3));ys=range(max(0,int(cy)-2),min(sh,int(cy)+3))
            neighbors=[(x,y) for y in ys for x in xs if dst[place_y+y,place_x+x,3]>0]
            if neighbors:
                selected=[min(neighbors,key=lambda p:(p[0]-cx)**2+(p[1]-cy)**2)]
        for x,y in selected:dst[place_y+y,place_x+x,:3]=feature['rgb']
        report.append({'name':feature['name'],'pixels':len(selected)})
    return report


def make_sprite(src:Image.Image,size=(48,48),max_colors=24,config=None,bg='auto',tolerance=26):
    if config is None:config={}
    W,H=size
    raw,fg,src_alpha=classify_fg(src,bg,tolerance)
    yy,xx=np.where(fg>0)
    bx0,bx1,by0,by1=int(xx.min()),int(xx.max())+1,int(yy.min()),int(yy.max())+1
    rgb=raw[by0:by1,bx0:bx1];mask=fg[by0:by1,bx0:bx1]
    padding=int(config.get('padding',1))
    scale=min((W-2*padding)/(bx1-bx0),(H-2*padding)/(by1-by0))
    nw=max(1,int(round((bx1-bx0)*scale)));nh=max(1,int(round((by1-by0)*scale)))
    ox=(W-nw)//2;oy=(H-nh)//2
    color,cov=area_color(rgb,mask,nw,nh)
    # Simple nearest baseline for objective comparison
    nearest_rgb=cv2.resize(rgb,(nw,nh),interpolation=cv2.INTER_NEAREST)
    nearest_m=cv2.resize(mask,(nw,nh),interpolation=cv2.INTER_NEAREST)>0
    base=np.zeros((H,W,4),dtype=np.uint8)
    base[oy:oy+nh,ox:ox+nw,:3]=nearest_rgb
    base[oy:oy+nh,ox:ox+nw,3]=nearest_m.astype(np.uint8)*255

    # Fractional area foreground coverage rather than crude black/white threshold.
    # Dual-threshold reconstruction only adds weak pixels connected to strong ones.
    strong=(cov>=float(config.get('coverage_threshold',.36))).astype(np.uint8)
    weak=(cov>=float(config.get('weak_threshold',.17))).astype(np.uint8)
    # Retain low-coverage pixels only beside the main hard mask (one dilation).
    dil=cv2.dilate(strong,np.ones((3,3),np.uint8),iterations=1)
    m=(strong|((weak>0)&(dil>0))).astype(np.uint8)
    if not np.any(m): m=(cov>=.15).astype(np.uint8)
    dst=np.zeros((H,W,4),np.uint8)
    dst[oy:oy+nh,ox:ox+nw,:3]=color
    dst[oy:oy+nh,ox:ox+nw,3]=m*255

    feats=[]
    for f in config.get('features',[]):
        if len(f.get('box',[]))!=4:continue
        detected=detect_feature_hints(rgb,mask,f,nw,nh)
        if detected:feats.append(detected)
    # Quantize backdrop down to remaining palette slots; last N reserved for feature colors.
    qsize=max(2,max_colors-len(set(tuple(map(int,x['rgb'])) for x in feats)))
    opaque=dst[:,:,3]>0
    dst[opaque,:3]=lab_quantize(dst[opaque,:3],qsize)
    feature_report=apply_features(dst,feats,ox,oy,nw,nh)
    # Deduplicate nearly identical outputs so the color count is provable.
    colors=len(np.unique(dst[opaque,:3],axis=0))
    assert colors<=max_colors,(colors,max_colors)
    assert np.all((dst[:,:,3]==0)|(dst[:,:,3]==255))
    metadata={'image_size':[W,H],'cropped_bbox':[bx0,by0,bx1,by1],
              'subject_scaled_size':[nw,nh],'subject_offset':[ox,oy],
              'colors':int(colors),'transparent':True,'src_had_alpha':bool(src_alpha),
              'feature_report':feature_report,'background_method':bg,
              'limits':'Plain background or alpha only; semantic feature ROIs are user-authored.'}
    return Image.fromarray(dst),Image.fromarray(base),metadata


def make_preview(basic,im,meta,outfile):
    W,H=im.size
    scale=min(8,max(2,576//max(W,H)))
    boxw=W*scale;boxh=H*scale
    side=2*boxw+48
    panel=Image.new('RGB',(side,boxh+114),(21,32,40))
    d=ImageDraw.Draw(panel)
    for idx,(src,label) in enumerate([(basic,'Nearest (baseline)'),(im,'B (protected)')]):
        x=16+idx*(boxw+16);y=36
        check=Image.new('RGB',(boxw,boxh),(42,53,58))
        c=ImageDraw.Draw(check)
        for j in range(0,boxh,24):
            for k in range(0,boxw,24):
                if ((j+k)//24)%2==0:c.rectangle((k,j,k+23,j+23),fill=(48,65,66))
        big=src.resize((boxw,boxh),Image.Resampling.NEAREST)
        check.paste(big,(0,0),big)
        panel.paste(check,(x,y))
        d.text((x,12),label,fill=(236,245,232))
        d.text((x,y+boxh+9),f'{W}x{H}',fill=(190,211,201))
        native=Image.new('RGBA',(W,H),(26,37,45,255));native.alpha_composite(src)
        panel.paste(native.convert('RGB'),(x+boxw-W,y+boxh+14))
    d.text((16,boxh+93),f'{meta["colors"]} colors | features: '+','.join(f['name']+':'+str(f['pixels']) for f in meta['feature_report']),fill=(177,209,188))
    panel.save(outfile,optimize=True)


def main():
    a=argparse.ArgumentParser(description='Pixelize source while protecting declared important features')
    a.add_argument('source',type=Path)
    a.add_argument('--size',type=parse_wh,default=(48,48))
    a.add_argument('--bg',choices=['auto','black','white'],default='auto')
    a.add_argument('--config',type=Path)
    a.add_argument('--out',type=Path,default=Path('B_sprite.png'))
    a.add_argument('--colors',type=int,default=24)
    a.add_argument('--tolerance',type=int,default=26)
    ns=a.parse_args()
    if not 4<=ns.colors<=48:raise ValueError('--colors must be 4..48')
    config=json.loads(ns.config.read_text(encoding='utf-8')) if ns.config else {}
    im,basic,meta=make_sprite(Image.open(ns.source),ns.size,ns.colors,config,ns.bg,ns.tolerance)
    ns.out.parent.mkdir(parents=True,exist_ok=True)
    im.save(ns.out,optimize=True)
    baseline=ns.out.with_name(ns.out.stem+'_nearest.png')
    basic.save(baseline,optimize=True)
    prev=ns.out.with_name(ns.out.stem+'_compare.png')
    make_preview(basic,im,meta,prev)
    ns.out.with_suffix('.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'sprite':str(ns.out),'preview':str(prev),**meta},ensure_ascii=False))

if __name__=='__main__':main()
