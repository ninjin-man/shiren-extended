from pathlib import Path
from PIL import Image, ImageDraw
from collections import Counter

OUT = Path(__file__).resolve().parent
W = H = 48
# Retained green / deep green / yellow-eye scheme; no brown.
C = {
    'ink': '#10240B',
    'outline': '#203D0C',
    'rim':'#356819',
    'shadow':'#225110',
    'deep':'#286915',
    'darkgreen':'#347D1A',
    'midgreen':'#448F1D',
    'body':'#58A928',
    'leaf':'#6CB82B',
    'grass':'#7BC82C',
    'lightgreen':'#8BD83A',
    'bright':'#A8EA3A',
    'lime':'#C6F03B',
    'yellowgreen':'#DDF754',
    'sheen':'#F1FA8A',
    'glint':'#FAFFC7',
    'inner':'#356F1B',
    'innerglow':'#B4DD37',
    'eyeShade':'#25390C',
    'eyeSocket':'#1B3710',
    'eyeBurn':'#8A9F19',
    'eye':'#F8D52B',
    'eyeLight':'#FFF2A4',
}
assert len(C) <= 24

def rgb(k): return tuple(bytes.fromhex(C[k][1:]))

# Geometry of a short, wave-crested head, a narrow flowing column and broad low puddle.
# The mask itself is rigorously symmetrical, while the streams / highlights are free-form.
half={
     4:1, 5:3, 6:4, 7:7, 8:9, 9:11, 10:12,
    11:13,12:14,13:15,14:16,15:16,16:16,17:15,18:14,
    19:12,20:10,21:8,22:6,23:5,24:5,25:5,26:5,
    27:5,28:5,29:6,30:6,31:7,32:8,33:10,34:13,
    35:16,36:19,37:21,38:22,39:22,40:21,41:19,
    42:16,43:12,44:7
}
mask=Image.new('L',(W,H),0)
m=ImageDraw.Draw(mask)
for y,hw in half.items():
    x0,x1=23-hw,24+hw
    m.line((x0,y,x1,y),fill=255)

# Pronounced hanging *solid* mucus curtains that extend beyond the tapered neck.
# Draw each lobe only once and mirror it to enforce the accepted symmetrical silhouette.
left_drips=[
  [(10,16),(11,16),(12,18),(12,21),(11,23),(10,24),(9,23),(9,20)],
  [(14,18),(16,19),(17,22),(17,26),(16,27),(15,26),(15,23),(14,21)],
  [(17,20),(20,21),(20,24),(19,26),(18,26),(18,24)],
]
for shp in left_drips:
    m.polygon(shp,fill=255)
    m.polygon([(47-x,y) for x,y in shp],fill=255)
# A scalloped brim, like a low-volume fountain lip.
for x,y in [(8,16),(8,17),(9,18),(10,19),(11,20),(12,21),(13,21),(14,22),
            (15,22),(16,23),(17,23),(18,24),(19,25),(20,26)]:
    m.point((x,y),fill=255)
    m.point((47-x,y),fill=255)
# Uneven-looking ridged crown: silhouette is symmetric, surface itself is not.
for x,y in [(18,6),(19,6),(20,5),(21,5),(22,4),(23,4)]:
    m.point((x,y),fill=255); m.point((47-x,y),fill=255)

im=Image.new('RGB',(W,H),rgb('body'))
d=ImageDraw.Draw(im)
def poly(coords,c): d.polygon(coords,fill=rgb(c))
def line(coords,c,w=1): d.line(coords,fill=rgb(c),width=w)
def pt(coords,c):
    for p in coords: d.point(p,fill=rgb(c))
def ell(rect,c): d.ellipse(rect,fill=rgb(c))

# Overall shaded volume, center-lit, dark on sides.
poly([(8,15),(15,8),(18,6),(18,14),(16,20),(18,27),(16,33),(5,39),(0,45),(0,13)],'darkgreen')
poly([(30,6),(37,14),(38,19),(35,25),(33,32),(47,38),(47,47),(40,42),(34,37),(29,30)],'deep')
poly([(17,7),(21,5),(26,5),(31,10),(30,16),(29,19),(28,21),(26,25),(26,30),(28,35),(36,40),(30,43),(19,43),(16,40),(21,35),(23,31),(20,26),(21,21),(19,17),(16,12)],'leaf')

# Swollen top, broken wax-like curved crest, NOT a spherical head.
poly([(16,12),(16,10),(18,7),(21,7),(24,9),(26,8),(29,8),(32,11),(32,13),(29,12),(27,13),(25,12),(22,13),(19,12)],'lightgreen')
poly([(17,9),(19,7),(22,7),(23,8),(20,9),(19,11),(17,11)],'bright')
poly([(24,7),(26,6),(28,7),(29,9),(27,10),(25,9)],'grass')
poly([(30,10),(32,11),(33,14),(31,15),(29,13)],'grass')
# Soft dark fold below irregular ridge
poly([(20,11),(23,11),(26,13),(29,12),(30,14),(28,15),(25,14),(23,15),(19,13)],'midgreen')

# Two large flowing sheets on the central fountain column.
poly([(18,19),(20,20),(21,23),(20,28),(19,31),(16,34),(10,37),(5,39),(8,40),(15,38),(20,36),(23,33),(24,29),(23,24),(22,21)],'deep')
poly([(29,20),(27,22),(26,25),(27,30),(30,34),(37,38),(42,39),(39,40),(32,38),(28,36),(25,32),(24,27)],'darkgreen')
# A continuous S-shaped viscous stream through neck to base.
poly([(22,19),(25,19),(27,21),(26,25),(25,27),(26,31),(29,34),(34,37),(39,39),(37,41),(31,40),(27,38),(23,34),(22,31),(21,28),(22,24)],'grass')
poly([(23,20),(25,21),(25,24),(24,27),(25,30),(27,33),(33,37),(35,38),(31,39),(26,36),(23,33),(22,29),(23,26)],'lightgreen')
poly([(23,24),(24,24),(23,28),(24,31),(26,34),(30,37),(27,37),(23,33),(22,30)],'bright')

# Left-facing flow line on the falling sheet
poly([(17,21),(18,21),(18,24),(18,29),(17,32),(13,35),(8,37),(7,39),(10,39),(16,36),(19,33),(20,29),(20,25)],'midgreen')
poly([(19,26),(20,28),(19,32),(16,35),(12,37),(11,38),(14,38),(19,35),(21,32),(22,30)],'grass')

# Puddle layers; ripples echo flowing source, no horizontal 'hat band'.
poly([(3,36),(12,35),(20,37),(24,38),(31,36),(41,36),(46,38),(43,40),(36,41),(30,43),(21,43),(16,42),(9,41),(3,39)],'deep')
poly([(4,37),(11,36),(17,37),(22,39),(28,38),(36,37),(43,38),(43,39),(36,40),(30,41),(24,42),(18,41),(12,40),(5,39)],'midgreen')
poly([(5,37),(10,37),(16,38),(22,40),(27,40),(33,39),(41,38),(41,39),(35,41),(28,42),(19,41),(14,40),(7,39)],'grass')
poly([(6,38),(11,38),(15,39),(18,40),(25,41),(30,41),(37,40),(40,39),(38,41),(32,42),(22,43),(14,41),(8,40)],'lightgreen')
# Arcing swirls at meeting point of stream and puddle
poly([(17,36),(20,35),(22,36),(26,38),(30,38),(33,39),(30,40),(25,39),(21,38),(18,38)],'bright')
poly([(11,39),(15,38),(18,39),(20,40),(16,40),(13,39)],'lime')
poly([(28,39),(33,38),(37,39),(34,40),(31,40)],'lime')

# Hanging taffy-like drips: strings with rounded ends and side highlights.
# They are green filaments, never transparent holes.
for coords in [
    [(12,17),(12,19),(13,21),(13,22)],
    [(16,19),(17,21),(17,24)],
    [(20,21),(20,24),(21,26)],
    [(29,19),(30,22),(30,25)],
    [(34,17),(34,20),(35,22)],
]:
    line(coords,'midgreen',3)
    line(coords,'lightgreen',1)
for x,y in [(13,22),(17,24),(21,26),(30,25),(35,22)]:
    ell((x-1,y-1,x+1,y+1),'lightgreen')
    pt([(x-1,y-1)],'sheen')

# Three soft occluded streams tucked behind the face, NOT black cavities.
poly([(14,19),(16,18),(17,20),(16,24),(16,27),(14,30),(14,25)],'shadow')
poly([(31,19),(33,19),(33,23),(32,26),(33,31),(30,28),(30,22)],'deep')
poly([(23,21),(24,22),(24,26),(23,28),(22,25)],'midgreen')

# Long viscous curtains glistening from the low irregular lip, with bulbous tips.
# The dark undersides carry across the border between the head and fountain.
poly([(10,18),(11,18),(12,20),(12,22),(11,23),(10,22)],'lightgreen')
pt([(10,21)],'sheen')
poly([(15,20),(16,20),(17,22),(17,25),(16,26),(15,24)],'grass')
line([(16,21),(16,24)],'lime')
pt([(16,25)],'sheen')
poly([(35,18),(36,18),(37,20),(37,22),(36,23),(35,21)],'lightgreen')
pt([(36,21)],'sheen')
poly([(30,20),(31,20),(32,22),(32,25),(31,26),(30,24)],'grass')
line([(31,21),(31,24)],'lime')
pt([(31,25)],'sheen')
# A small curving ledge across the face, broken instead of a hat-shaped horizontal band.
poly([(13,19),(16,19),(18,20),(18,22),(16,22),(15,21)],'bright')
poly([(29,20),(31,19),(34,19),(33,21),(31,22),(29,22)],'lightgreen')
pt([(15,19),(33,20)],'sheen')

# Hostile eyes: dark tilted sockets, small yellow eyes under downward brows.
poly([(14,14),(16,13),(20,15),(21,17),(19,19),(16,19),(14,17)],'eyeShade')
poly([(27,15),(31,13),(33,14),(34,17),(32,19),(29,19),(27,17)],'eyeShade')
poly([(15,15),(17,15),(20,16),(19,18),(16,18)],'eyeSocket')
poly([(28,16),(31,15),(33,15),(32,18),(29,18)],'eyeSocket')
poly([(16,16),(18,16),(19,17),(18,18),(17,18)],'eye')
poly([(29,17),(30,16),(32,16),(31,18),(30,18)],'eye')
pt([(17,16),(31,16)],'eyeLight')
line([(14,14),(16,13),(20,15),(21,16)],'outline',1)
line([(27,16),(28,15),(31,13),(33,14)],'outline',1)
# Luminous slime brows that arch downward toward center
line([(14,13),(16,12),(18,13),(20,14)],'bright',1)
line([(28,14),(30,13),(32,12),(34,13)],'lime',1)

# Wet layers above face and along three paths, in small meaningful patches.
poly([(17,8),(19,7),(21,7),(20,8),(19,10),(17,10)],'yellowgreen')
pt([(18,8),(19,7),(21,8)],'glint')
poly([(26,7),(28,7),(29,8),(28,9),(26,9)],'lime')
pt([(27,7)],'sheen')
line([(12,13),(13,11),(14,10)],'lime')
pt([(13,11)],'glint')
poly([(34,14),(35,14),(36,16),(35,17),(34,16)],'bright')
pt([(35,15)],'sheen')
# lip lighting in broken arcs (never one full-width straight stripe)
line([(12,19),(14,20),(16,19)],'bright')
line([(18,21),(20,22),(21,24)],'lime')
line([(29,20),(31,21),(33,19)],'lightgreen')
pt([(14,20),(20,22),(32,20)],'sheen')
# Long descending glossy trails taper into the pool.
poly([(18,28),(19,27),(19,30),(18,33),(15,36),(12,38),(13,36),(17,32)],'bright')
pt([(18,29),(17,33),(15,35)],'sheen')
poly([(24,27),(25,29),(25,32),(27,35),(31,38),(29,38),(25,35),(23,32)],'lime')
pt([(24,29),(26,34)],'sheen')
poly([(29,32),(30,34),(34,37),(37,38),(36,39),(32,37)],'bright')
pt([(31,35),(35,38)],'sheen')

# Ring of fluid speculars distributed around the lowest puddle, and rim.
line([(5,38),(8,37),(11,37)],'yellowgreen')
line([(13,40),(17,40),(20,41)],'yellowgreen')
line([(25,42),(29,41),(32,41)],'lime')
line([(36,39),(40,38),(43,38)],'yellowgreen')
pt([(6,38),(9,37),(17,40),(27,42),(37,39),(42,38)],'sheen')

# Occlusion/contour edge derived ONLY after the internal material is fully constructed.
source=im.load(); srcmask=mask.load()
result=Image.new('RGBA',(W,H),(0,0,0,0))
out=result.load()
for y in range(H):
    for x in range(W):
        if not srcmask[x,y]: continue
        neigh=[(x-1,y),(x+1,y),(x,y-1),(x,y+1)]
        edge=any(xx<0 or xx>=W or yy<0 or yy>=H or not srcmask[xx,yy] for xx,yy in neigh)
        if edge:
            out[x,y]=rgb('ink')+(255,)
            continue
        near=any(any(xx<0 or xx>=W or yy<0 or yy>=H or not srcmask[xx,yy]
                     for xx,yy in [(nx-1,ny),(nx+1,ny),(nx,ny-1),(nx,ny+1)])
                 for nx,ny in neigh if 0<=nx<W and 0<=ny<H and srcmask[nx,ny])
        if near:
            out[x,y]=rgb('rim')+(255,)
        else:
            out[x,y]=source[x,y]+(255,)

# Small outer droplets deliberately not touching outline.
rd=ImageDraw.Draw(result)
for (x,y,r) in [(8,28,1),(39,28,1),(10,32,0),(37,32,0)]:
    rd.ellipse((x-r-1,y-r-1,x+r+1,y+r+1),fill=rgb('outline')+(255,))
    rd.ellipse((x-r,y-r,x+r,y+r),fill=rgb('grass')+(255,))
    rd.point((x-r,y-r),fill=rgb('sheen')+(255,))

# Keep accidental detached artifacts out of the main mass (intentional separate droplets above).
assert all(bool(out[x,y][3])==bool(out[47-x,y][3]) for y in range(48) for x in range(24) if 0<=x<=47)
used={v[:3] for v,n in Counter(result.getdata()).items() if v[3]}
assert all(v[3] in (0,255) for v in result.getdata())
assert len(used)<=24,(len(used),used)
result.save(OUT/'midoro_fountain_48_v3.png', optimize=True)
zoom=result.resize((576,576),Image.Resampling.NEAREST)
# checkerboard-like colored backing to distinguish true transparency
back=Image.new('RGB',(576,576),'#172330')
bd=ImageDraw.Draw(back)
for y in range(0,576,48):
    for x in range(0,576,48):
        if ((x+y)//48)%2: bd.rectangle((x,y,x+47,y+47),fill='#213241')
back.paste(zoom,(0,0),zoom)
back.save(OUT/'midoro_fountain_48_v3_zoom.png',optimize=True)
print('colors',len(used),'symmetric alpha','native 48x48')
