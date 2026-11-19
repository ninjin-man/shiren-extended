#!/usr/bin/env python3
"""v07 experimental topology-first closed regions for bucket-fill preparation.

Independent deterministic implementation: NumPy, OpenCV and Pillow only.
Does not use pretrained models, network, or external research code.
No object-specific coordinates, labels, or class assumptions.

Examples:
  python curve_structure_v07.py input/sword.png --output results/sword --width 560 --colors 16 --min-island 45
  python curve_structure_v07.py input/elf.png --output results/elf --width 560 --colors 18 --min-island 45

IMPORTANT: This is a structural bucket-fill scaffold, not finished anime lineart.
Source-ink strokes and source-color regions are distinguished in outputs.
The closed-wall version is tested for 8-neighbor bucket fill.
The lossless `06_region_ids.png` provides a second programmatic selection path.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from collections import Counter
import cv2
import numpy as np
from PIL import Image, ImageDraw


def prepare(path, width):
    image=Image.open(path).convert('RGBA')
    newsize=(width,max(16,round(image.height*width/image.width)))
    raw=np.asarray(image.resize(newsize,Image.Resampling.LANCZOS)).copy()
    af=raw[:,:,3].astype(np.float32)/255
    rgb=(raw[:,:,:3].astype(np.float32)*af[:,:,None]+255*(1-af[:,:,None])).clip(0,255).astype(np.uint8)
    if np.any(raw[:,:,3]<245):
        # Real transparency available; respect it; discard anti-aliased fringe.
        fg=raw[:,:,3]>=80
        method='alpha'
    else:
        hsv=cv2.cvtColor(rgb,cv2.COLOR_RGB2HSV)
        # Only nearly-white contiguous background, not arbitrary pale clothing.
        cand=(np.min(rgb,axis=2)>239) & (hsv[:,:,1]<32)
        h,w=cand.shape
        n,labels=cv2.connectedComponents(cand.astype(np.uint8),4)
        edge=np.r_[labels[0],labels[-1],labels[:,0],labels[:,-1]]
        counts=Counter(edge.tolist());counts.pop(0,None)
        bg_label=max(counts,key=counts.get) if counts else -1
        bg=labels==bg_label
        fg=~bg
        method='connected-white'
    return rgb,fg,method


def clustered_materials(rgb,fg,color_count=18):
    """Classify *color fields* not semantics. Kmeans only trained on foreground."""
    filtered=cv2.bilateralFilter(rgb,7,28,9)
    lab=cv2.cvtColor(filtered,cv2.COLOR_RGB2LAB)
    ys,xs=np.where(fg)
    if ys.size==0:raise ValueError('No foreground extracted')
    rng=np.random.default_rng(614)
    # Include uniformly distributed spatial and strong-color source examples.
    indices=rng.choice(len(xs),min(16000,len(xs)),replace=False)
    samples=lab[ys[indices],xs[indices]].astype(np.float32)
    k=min(color_count,len(np.unique(samples,axis=0)))
    cv2.setRNGSeed(614)
    _,_,centers=cv2.kmeans(samples,int(k),None,(cv2.TERM_CRITERIA_MAX_ITER+cv2.TERM_CRITERIA_EPS,45,.25),3,cv2.KMEANS_PP_CENTERS)
    # stable order by lightness; makes diagnostics easier to inspect
    centers=np.array(sorted(centers,key=lambda c:(float(c[0]),float(c[1]),float(c[2]))),np.float32)
    label=np.full(fg.shape,-1,np.int16)
    ys,xs=np.where(fg)
    for start in range(0,len(xs),16000):
        yy,xx=ys[start:start+16000],xs[start:start+16000]
        points=lab[yy,xx].astype(np.float32)
        d=np.sum((points[:,None,:]-centers[None,:,:])**2,axis=2)
        label[yy,xx]=np.argmin(d,axis=1).astype(np.int16)
    return label,centers,filtered


def component_ids(labels,fg):
    """Unique ID for connected pieces of equal material; -1 for background."""
    h,w=labels.shape
    piece=np.full((h,w),-1,np.int32)
    infos=[]
    next_id=0
    for clr in np.unique(labels[fg]):
        n,ids,stats,cent=cv2.connectedComponentsWithStats(((labels==clr)&fg).astype('uint8'),8)
        for i in range(1,n):
            area=int(stats[i,cv2.CC_STAT_AREA])
            x,y,ww,hh=[int(v) for v in stats[i,:4]]
            local=ids[y:y+hh,x:x+ww]==i
            view=piece[y:y+hh,x:x+ww]
            view[local]=next_id
            infos.append((next_id,int(clr),area,(x,y,ww,hh)))
            next_id+=1
    return piece,infos


def remove_very_tiny_regions(labels,fg,centers,min_area=45):
    """Conservative label merging; protects high-contrast tiny details.

    This changes *material labels* only, not source RGB. No fantasy-object rules.
    """
    clean=labels.copy()
    merged=0
    for _ in range(2):
        piece,infos=component_ids(clean,fg)
        modified=0
        for pid,col,area,(x,y,ww,hh) in sorted(infos,key=lambda x:x[2]):
            if area>=min_area:continue
            x0=max(0,x-1);y0=max(0,y-1);x1=min(clean.shape[1],x+ww+1);y1=min(clean.shape[0],y+hh+1)
            mask=(piece[y0:y1,x0:x1]==pid).astype('uint8')
            surrounding=(cv2.dilate(mask,np.ones((3,3),np.uint8))>0) & (mask==0)
            around=clean[y0:y1,x0:x1][surrounding]
            around=around[around>=0]
            if not around.size:continue
            hist=Counter(around.tolist())
            labdist=np.linalg.norm(centers[np.asarray(list(hist.keys()))]-centers[col],axis=1)
            # Small region of very different color is potentially eye/jewel/mark; keep if visible.
            if area>=9 and (float(labdist.min())>=42):continue
            # Use border contact first with perceptual color similarity second.
            options=[(cnt-.22*np.linalg.norm(centers[other]-centers[col]),other) for other,cnt in hist.items()]
            dest=max(options)[1]
            curr=clean[y0:y1,x0:x1]
            curr[mask>0]=dest
            modified+=1
        merged+=modified
        if modified==0:break
    return clean,merged


def closed_wall(labels,fg):
    """For every 4-neighbor label transition, at least one pixel is a wall.

    Produces a 1px wall, placed in the darker side of each boundary when both
    pixels are foreground, and always inside the subject at its silhouette.
    Guarantees that 4-connected flood fill cannot cross region ID transitions.
    """
    h,w=fg.shape
    wall=np.zeros((h,w),bool)
    # Both labels and foreground are encoded, background=-1.
    labs=labels.copy();labs[~fg]=-1
    # Mark exactly one side of every pixel edge that spans different labels.
    def handle(a,b,fga,fgb,wa,wb):
        changed=a!=b
        # choose foreground pixel for silhouette, dark-side or deterministic inside for material boundary
        to_a=changed & fga & (~fgb | ((fgb)&(a<=b)))
        to_b=changed & fgb & (~fga | ((fga)&(b<a)))
        wa |= to_a;wb |= to_b
    handle(labs[:,:-1],labs[:,1:],fg[:,:-1],fg[:,1:],wall[:,:-1],wall[:,1:])
    handle(labs[:-1,:],labs[1:,:],fg[:-1,:],fg[1:,:],wall[:-1,:],wall[1:,:])
    # A transparent figure near frame edges still needs a closing frame boundary.
    wall[0,:]|=fg[0,:];wall[-1,:]|=fg[-1,:]
    wall[:,0]|=fg[:,0];wall[:,-1]|=fg[:,-1]
    return wall


def bridge_diagonals_for_8fill(wall, fg):
    """Join diagonal line pixels with orthogonal bridge, so 8-neighbor fill
    cannot squeeze between pixels joined only at the corner. Deterministic.
    Prefer adding a foreground pixel to preserve exterior background.
    """
    w=wall.copy()
    for _ in range(3):
        a=w[:-1,:-1]; b=w[:-1,1:]; c=w[1:,:-1]; d=w[1:,1:]
        diag_down=a & d & (~b) & (~c)
        diag_up=b & c & (~a) & (~d)
        count=int(diag_down.sum()+diag_up.sum())
        if count==0:break
        extra=np.zeros(w.shape,bool)
        # For \ diagonal: bridge above-right when foreground; otherwise bottom-left.
        top=np.where(diag_down & (fg[:-1,1:] | ~fg[1:,:-1]),True,False)
        extra[:-1,1:] |= diag_down & top
        extra[1:,:-1] |= diag_down & (~top)
        # For / diagonal: bridge above-left when foreground; otherwise bottom-right.
        top=np.where(diag_up & (fg[:-1,:-1] | ~fg[1:,1:]),True,False)
        extra[:-1,:-1] |= diag_up & top
        extra[1:,1:] |= diag_up & (~top)
        w |= extra
    return w


def make_ink_stroke(rgb,fg):
    """Very conservative diagnostic: existing dark ink-like local bands.

    Does not change the topology/region map. Useful as a separately editable
    layer, rather than forcing its open ends to close arbitrary regions.
    """
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    close=cv2.morphologyEx(gray,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(9,9)))
    blackhat=(close.astype(np.int16)-gray.astype(np.int16))
    ink=(blackhat>=18) & (gray<152) & fg
    return ink


def validate_fills(wall, labels, fg, min_large=50):
    white=(~wall).astype('uint8')
    n,cc,stats,_=cv2.connectedComponentsWithStats(white,connectivity=8)
    outside_ids=set(int(v) for v in np.r_[cc[0,:],cc[-1,:],cc[:,0],cc[:,-1]] if v>0)
    region_components=[]
    mixed_components=0
    mixed_area=0
    for rid in range(1,n):
        if rid in outside_ids:continue
        x,y,ww,hh,area=[int(v) for v in stats[rid]]
        mask=(cc[y:y+hh,x:x+ww]==rid)&fg[y:y+hh,x:x+ww]
        vals=np.unique(labels[y:y+hh,x:x+ww][mask])
        if len(vals)>1:
            mixed_components+=1;mixed_area+=area
        if area>=min_large:
            region_components.append((rid,area,x,y,ww,hh))
    # Leakage: any source foreground pixel of non-wall sharing the exterior ID.
    outside=np.isin(cc,list(outside_ids))
    fg_unsealed=fg & (~wall) & outside
    return {'fillable_closed_regions_over_50px':len(region_components),
            'total_fillable_regions':int(n-1-len(outside_ids)),
            'region_crossings':mixed_components,
            'crossing_area_px':mixed_area,
            'foreground_pixels_reachable_from_outside':int(fg_unsealed.sum()),
            'large_region_areas':[int(r[1]) for r in sorted(region_components,key=lambda r:r[1],reverse=True)[:12]]},cc,region_components


def preview(src,old,region_preview,line,fill,paths,out):
    width=520
    panels=[('ORIGINAL',src),('V06 STROKE-ONLY (NOT FILLABLE)',old),
            ('V07 CLOSED REGIONS / ID VIEW',region_preview),('V07 CLOSED BUCKET-FILL LINEWORK',line),
            ('V07 8-NEIGHBOR BUCKET-FILL RESULT',fill)]
    resized=[]
    for title,im in panels:
        h=max(30,round(im.height*width/im.width))
        resized.append((title,im.resize((width,h),Image.Resampling.LANCZOS)))
    height=sum(im.height+38 for _,im in resized)+20
    canvas=Image.new('RGB',(width+26,height),(243,243,241))
    d=ImageDraw.Draw(canvas)
    y=15
    for title,im in resized:
        d.text((13,y),title,fill=(35,39,43));y+=20
        canvas.paste(im,(13,y));y+=im.height+18
    canvas.save(out/'iphone_review.jpg',quality=92,subsampling=0)


def run(source,out,width=560,colors=18,min_island=45,oldline=None):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    rgb,fg,mode=prepare(source,width)
    lbl,centers,filtered=clustered_materials(rgb,fg,colors)
    label,merged=remove_very_tiny_regions(lbl,fg,centers,min_island)
    # IDs track actual contiguous paintable regions, NOT semantic object names.
    region_id,infos=component_ids(label,fg)
    wall_base=closed_wall(region_id,fg)
    wall=bridge_diagonals_for_8fill(wall_base,fg)
    metrics,cc,large=validate_fills(wall,region_id,fg)
    # All white regions are flood-filled from cc labels, not interpolated colors.
    cols=np.asarray([(29+(i*67)%195,43+(i*101)%190,62+(i*43)%179) for i in range(max(1,len(infos)))],np.uint8)
    vis=np.full(rgb.shape,255,np.uint8)
    vis[region_id>=0]=cols[region_id[region_id>=0]]
    vis[wall]=[34,37,43]
    fill_colors=np.zeros(rgb.shape,np.uint8);fill_colors[:]=255
    # Actual 8-neighbor flood-fill demonstration: one FLAT RGB color per
    # connected white area of the closed lineart, sampled from original.
    H,W=fg.shape
    component_count,_,component_stats,_=cv2.connectedComponentsWithStats((~wall).astype('uint8'),connectivity=8)
    outside_ids=set(int(v) for v in np.r_[cc[0],cc[-1],cc[:,0],cc[:,-1]] if v>0)
    for rid in range(1,component_count):
        if rid in outside_ids:continue
        x,y,ww,hh,area=[int(v) for v in component_stats[rid]]
        place=cc[y:y+hh,x:x+ww]==rid
        palette=np.median(rgb[y:y+hh,x:x+ww][place],axis=0).astype(np.uint8)
        fill_colors[y:y+hh,x:x+ww][place]=palette
    fill_colors[wall]=[23,25,30]
    black=np.full(rgb.shape,255,np.uint8);black[wall]=[20,22,28]
    # Original ink is a distinct layer. It is deliberately not merged into fill walls.
    ink=make_ink_stroke(rgb,fg)
    inkvis=np.zeros((*fg.shape,4),np.uint8);inkvis[ink]=[30,32,37,255]
    Image.fromarray(rgb).save(out/'00_original.png')
    Image.fromarray(vis).save(out/'01_regions_closed.png')
    Image.fromarray(black).save(out/'02_closed_lineart.png')
    Image.fromarray(fill_colors).save(out/'03_bucket_filled.png')
    Image.fromarray(inkvis).save(out/'04_original_ink_layer.png')
    Image.fromarray(np.where(wall,255,0).astype('uint8')).save(out/'05_wall_mask.png')
    # Lossless region ids for reliable programmatic fill (if 8-connectivity desired).
    regionpng=np.zeros((H,W,4),np.uint8)
    u=region_id+1
    regionpng[:,:,0]=(u & 255).astype('uint8')
    regionpng[:,:,1]=((u>>8)&255).astype('uint8')
    regionpng[:,:,2]=((u>>16)&255).astype('uint8')
    regionpng[:,:,3]=np.where(fg,255,0).astype('uint8')
    Image.fromarray(regionpng,'RGBA').save(out/'06_region_ids.png')
    if oldline and Path(oldline).exists():
        old=Image.open(oldline).convert('RGB').resize((W,H),Image.Resampling.NEAREST)
    else:
        old=Image.new('RGB',(W,H),'white')
    preview(Image.fromarray(rgb),old,Image.fromarray(vis),Image.fromarray(black),Image.fromarray(fill_colors),None,out)
    metrics.update({'source':str(source),'width':W,'height':H,'background_method':mode,
        'palette_colors':colors,'label_regions_initial':len(component_ids(lbl,fg)[1]),
        'label_regions_after_merge':len(infos),'merged_tiny_regions':merged,
        'closed_line_pixels':int(wall.sum()),'diagonal_bridge_pixels':int((wall&~wall_base).sum()),'source_stroke_candidates':int(ink.sum()),
        'limits':['8-neighbor closed-line bucket fill is verified algorithmically; use region ID PNG for stronger programmatic selection.',
            'Closed material boundaries are topological guides, NOT guaranteed to be hand-drawn ink.',
            'This is a structural/fillability prototype, not finished anime-style clean linework or semantic segmentation.']})
    (out/'report.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding='utf-8')
    return metrics


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source');p.add_argument('--output',default='v07_results');p.add_argument('--width',type=int,default=560)
    p.add_argument('--colors',type=int,default=18);p.add_argument('--min-island',type=int,default=45)
    p.add_argument('--oldline',default=None)
    a=p.parse_args()
    m=run(a.source,a.output,a.width,a.colors,a.min_island,a.oldline)
    print(json.dumps(m,ensure_ascii=False))
if __name__=='__main__':main()
