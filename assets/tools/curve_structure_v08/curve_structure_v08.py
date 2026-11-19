#!/usr/bin/env python3
"""v08: actual drawing-stroke layer + independent hidden, 8-connected fill topology.

Reuses our own v07 algorithms for topology. The visible art never blindly
renders every material boundary as a black stroke. No network, AI, third-party
research code, or object-specific pixels. Dependencies: numpy, opencv, Pillow.

Example: python curve_structure_v08.py input.png --out output --width 560 --colors 18
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import cv2
from PIL import Image, ImageDraw
from curve_structure_v07 import (prepare, clustered_materials, remove_very_tiny_regions,
    component_ids, closed_wall, bridge_diagonals_for_8fill, validate_fills)


def remove_small(mask, min_area):
    n,l,s,_=cv2.connectedComponentsWithStats(mask.astype(np.uint8),8)
    keep=np.zeros(mask.shape, np.uint8)
    for i in range(1,n):
        if s[i,cv2.CC_STAT_AREA]>=min_area: keep[l==i]=1
    return keep.astype(bool)


def skeleton_zhang(mask, max_rounds=65):
    """Two-pass topology-preserving thinning of ink *bands* (not Canny edges)."""
    x=mask.astype(np.uint8).copy()
    x[[0,-1],:]=0;x[:,[0,-1]]=0
    for _ in range(max_rounds):
        changes=0
        for phase in range(2):
            p2=x[:-2,1:-1]; p3=x[:-2,2:]; p4=x[1:-1,2:]
            p5=x[2:,2:]; p6=x[2:,1:-1]; p7=x[2:,:-2]
            p8=x[1:-1,:-2]; p9=x[:-2,:-2]; c=x[1:-1,1:-1]
            n=p2+p3+p4+p5+p6+p7+p8+p9
            trans=((p2==0)&(p3==1)).astype(np.uint8)
            for a,b in ((p3,p4),(p4,p5),(p5,p6),(p6,p7),(p7,p8),(p8,p9),(p9,p2)):
                trans+=((a==0)&(b==1)).astype(np.uint8)
            if phase==0: cond=((p2*p4*p6)==0)&((p4*p6*p8)==0)
            else: cond=((p2*p4*p8)==0)&((p2*p6*p8)==0)
            rem=(c==1)&(n>=2)&(n<=6)&(trans==1)&cond
            changes+=int(rem.sum());c[rem]=0
        if changes==0: break
    return x>0


def source_stroke_layers(rgb, fg, detail='balanced'):
    """Locally identify pigment bands vs ordinary shading edges.

    Intensity-valley centerlines are separated from pure region boundaries.
    Preserve a conservative subset of genuine sharp interior edges for faint
    hair/eyes while avoiding parallel edges on thick pigment strokes.
    """
    H,W=fg.shape
    g=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    gs=g.astype(np.float32)
    sizes=[max(5,int(round(W*.010))|1),max(9,int(round(W*.018))|1)]
    bh=[]
    for k in sizes:
        bh.append(cv2.morphologyEx(g,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(k,k))).astype(np.float32)-gs)
    deficit=np.maximum(bh[0],.72*bh[1])
    local=cv2.GaussianBlur(gs,(0,0),3.2)
    local_dark=local-gs
    # Dark line and pale-pigment bands are both locally darker than surroundings.
    # Avoid promoting broad monotonic shading boundaries to ink.
    strong=(deficit>=15)&(local_dark>=7)&(gs<197)&fg
    pale=(deficit>=26)&(local_dark>=11)&(gs<225)&fg
    pigment=remove_small(strong|pale,5)
    center=skeleton_zhang(pigment)
    center=remove_small(center,5)
    # Include real color-ink evidence from sharp, high-gradient edges ONLY where
    # it does not create a parallel contour beside the already found pigment.
    # This rescue is conservative; otherwise B style becomes all shading lines.
    lab=cv2.cvtColor(rgb,cv2.COLOR_RGB2LAB)
    l,a,b=cv2.split(lab)
    clahe=cv2.createCLAHE(clipLimit=1.5,tileGridSize=(8,8))
    adapted=clahe.apply(g)
    base=cv2.Canny(cv2.GaussianBlur(g,(3,3),.8),65 if detail=='detailed' else 78,140 if detail=='detailed' else 155,L2gradient=True)>0
    adaptive=cv2.Canny(cv2.GaussianBlur(adapted,(3,3),.8),90,177,L2gradient=True)>0
    extra=(base | (adaptive & (deficit>=12)))&fg
    # Avoid double-edge on wide brush strokes; use the pigment skeleton instead.
    near=cv2.dilate(pigment.astype(np.uint8),np.ones((5,5),np.uint8))>0
    extra &= ~near
    # A material edge alone is not evidence of an ink stroke. Limit recovery
    # to the vicinity of confirmed local pigment, not every Canny boundary.
    nearby_center=cv2.dilate(center.astype(np.uint8),np.ones((13,13),np.uint8))>0
    extra &= nearby_center
    # Canny on gradations can dominate: keep strong contrast only.
    sx=cv2.Sobel(gs,cv2.CV_32F,1,0,ksize=3)
    sy=cv2.Sobel(gs,cv2.CV_32F,0,1,ksize=3)
    grad=cv2.magnitude(sx,sy)
    extra &= grad>(105 if detail=='detailed' else 145)
    extra=remove_small(extra,10 if detail=='detailed' else 16)
    # Do not draw every outer silhouette if the original has NO drawn stroke.
    # For inked art, use observed painted bands; nearest outline not invented.
    visible=center|extra
    # No-outline illustrations must not acquire black strokes from pure color
    # boundaries. Sparse candidate specks do not justify stroke rendering.
    if int(center.sum()) < max(40,int(fg.sum()*.00038)):
        center[:]=False;extra[:]=False;visible[:]=False
    return visible,center,extra,deficit



def compact_feature_lines(rgb,fg,regions,infos,existing):
    """Preserve tiny high-contrast regions (iris, gem, markings) as outline.

    Uses color contrast, area and compactness, NEVER class/name/coordinates.
    Does not paint other material boundaries. This is a heuristic, not semantic
    feature detection; excess decoration remains a possible false positive.
    """
    lab=cv2.cvtColor(rgb,cv2.COLOR_RGB2LAB).astype(np.float32)
    kept=np.zeros(fg.shape,bool)
    accepted=0
    H,W=fg.shape
    for rid,_,area,(x,y,w,h) in infos:
        if area<18 or area>220 or max(w,h)>30 or max(w,h)/max(1,min(w,h))>4:
            continue
        x0=max(0,x-3); y0=max(0,y-3)
        x1=min(W,x+w+3);y1=min(H,y+h+3)
        roi=(regions[y0:y1,x0:x1]==rid)
        near=(cv2.dilate(roi.astype(np.uint8),np.ones((5,5),np.uint8))>0)&(~roi)&fg[y0:y1,x0:x1]
        if near.sum()<max(8,roi.sum()*.15):continue
        inside=np.median(lab[y0:y1,x0:x1][roi],axis=0)
        outside=np.median(lab[y0:y1,x0:x1][near],axis=0)
        difference=float(np.linalg.norm(inside-outside))
        if difference<72 or (outside[0]-inside[0])<35:
            continue
        # inside border of this actual color region (only 1px)
        edge=roi & (cv2.erode(roi.astype(np.uint8),np.ones((3,3),np.uint8))==0)
        # preserve real small detail but do not widen or duplicate existing ink
        patch=kept[y0:y1,x0:x1]
        patch |= edge & (cv2.dilate(existing[y0:y1,x0:x1].astype(np.uint8),np.ones((3,3),np.uint8))==0)
        accepted+=1
    return kept,accepted

def visible_png(mask,fg,transparent=False):
    if transparent:
        arr=np.zeros((*mask.shape,4),np.uint8)
        arr[:,:,:3]=[29,29,33]
        arr[:,:,3]=np.where(mask,255,0).astype(np.uint8)
    else:
        arr=np.full((*mask.shape,3),255,np.uint8)
        arr[mask]=[29,29,33]
    return Image.fromarray(arr,'RGBA' if transparent else 'RGB')


def fill_by_region(rgb,fg,wall):
    # Actual 8-neighbor flood-fill connected components from wall mask; fills
    # each closed region with a single source median color. RGB output is useful
    # to demonstrate that visible art need not include all fill walls.
    n,cc,stats,_=cv2.connectedComponentsWithStats((~wall).astype('uint8'),connectivity=8)
    exterior=set(int(v) for v in np.r_[cc[0],cc[-1],cc[:,0],cc[:,-1]] if v>0)
    out=np.full(rgb.shape,255,np.uint8)
    for i in range(1,n):
        if i in exterior:continue
        x,y,w,h,area=[int(v) for v in stats[i]]
        m=(cc[y:y+h,x:x+w]==i)
        vals=rgb[y:y+h,x:x+w][m]
        if vals.size:
            color=np.median(vals,axis=0).astype(np.uint8)
            out[y:y+h,x:x+w][m]=color
    # Fill invisible wall pixels from neighboring flat-colored areas, rather
    # than leaving white seams. The region ID mask remains lossless.
    wall_u8=wall.astype(np.uint8)*255
    if wall_u8.any():
        out=cv2.inpaint(out,wall_u8,2,cv2.INPAINT_TELEA)
    return out


def make_preview(source,old,wall,visible,filled,combined,out):
    panels=[('ORIGINAL',source),('V07 ALL COLOR BOUNDARIES',old),
            ('V08 VISIBLE STROKES',visible),('V08 HIDDEN BUCKET WALLS',wall),
            ('V08 FLAT COLORS (WALLS HIDDEN)',filled),('VISIBLE LINES + FLAT COLOR',combined)]
    disp_w=520; new=[]
    for name,im in panels:
        h=max(10,round(im.height*disp_w/im.width))
        new.append((name,im.resize((disp_w,h),Image.Resampling.LANCZOS)))
    H=sum(im.height+40 for _,im in new)+20
    sheet=Image.new('RGB',(disp_w+24,H),(243,243,241))
    d=ImageDraw.Draw(sheet)
    y=15
    for title,im in new:
        d.text((12,y),title,fill=(25,30,36));y+=18
        sheet.paste(im,(12,y));y+=im.height+22
    sheet.save(out/'06_iphone_review.jpg',quality=90,subsampling=0)


def run(source,out,width=560,colors=18,min_island=45,detail='detailed'):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    rgb,fg,bg_method=prepare(source,width)
    label,centers,filtered=clustered_materials(rgb,fg,colors)
    clean,merged=remove_very_tiny_regions(label,fg,centers,min_island)
    regions,infos=component_ids(clean,fg)
    wall0=closed_wall(regions,fg)
    wall=bridge_diagonals_for_8fill(wall0,fg)
    metrics,cc,closed=validate_fills(wall,regions,fg)
    visible,center,extra,deficit=source_stroke_layers(rgb,fg,detail=detail)
    features,feature_count=compact_feature_lines(rgb,fg,regions,infos,visible)
    # Compact region lines only matter when a real ink drawing was detected.
    # This prevents false black features in otherwise line-free illustrations.
    if int(center.sum())>max(40,int(fg.sum()*.00038)):
        visible |= features
    paint=fill_by_region(rgb,fg,wall)
    composite=paint.copy();composite[visible]=[29,29,33]
    white_line=visible_png(visible,fg)
    wall_line=visible_png(wall,fg)
    pngmap=np.zeros((*fg.shape,4),dtype=np.uint8)
    packed=regions+1
    pngmap[:,:,0]=(packed&255).astype('uint8')
    pngmap[:,:,1]=((packed>>8)&255).astype('uint8')
    pngmap[:,:,2]=((packed>>16)&255).astype('uint8')
    pngmap[:,:,3]=np.where(fg,255,0).astype('uint8')
    Image.fromarray(rgb).save(out/'00_original.png')
    white_line.save(out/'01_visible_lineart.png')
    visible_png(visible,fg,True).save(out/'01_visible_lineart_alpha.png')
    wall_line.save(out/'02_hidden_closed_wall_preview.png')
    Image.fromarray(pngmap,'RGBA').save(out/'03_region_ids_lossless.png')
    Image.fromarray(paint).save(out/'04_flat_fill_no_walls.png')
    Image.fromarray(composite).save(out/'05_visible_lines_and_fill.png')
    # comparison with *previous saved* v07 when available, otherwise computed wall.
    make_preview(Image.fromarray(rgb),wall_line,wall_line,white_line,Image.fromarray(paint),Image.fromarray(composite),out)
    report={**metrics, 'source':str(source), 'size':list(white_line.size),
        'foreground_pixels':int(fg.sum()),'color_region_ids':len(infos),'tiny_region_merges':merged,
        'visible_stroke_pixels':int(visible.sum()),'compact_feature_candidates':int(feature_count),'new_feature_line_pixels':int((visible & features).sum()),'pigment_center_pixels':int(center.sum()),
        'additional_sharp_line_pixels':int(extra.sum()),'hidden_wall_pixels':int(wall.sum()),
        'background_method':bg_method,
        'notes':['Visible stroke layer and watertight fill map are separate. Visible layer is not necessarily flood-fill-closed.',
                 'Lossless region IDs and hidden walls allow guaranteed bucket selection even if visible ink has open ends.',
                 'Color regions are not semantic body parts. Individual visible strokes can still be missed.',
                 'No external research code or model used.']}
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument('source');p.add_argument('--out',default='v08_out')
    p.add_argument('--width',type=int,default=560);p.add_argument('--colors',type=int,default=18)
    p.add_argument('--min-island',type=int,default=45)
    p.add_argument('--detail',choices=['balanced','detailed'],default='detailed')
    args=p.parse_args()
    print(json.dumps(run(args.source,args.out,args.width,args.colors,args.min_island,args.detail),ensure_ascii=False))
if __name__=='__main__':main()
