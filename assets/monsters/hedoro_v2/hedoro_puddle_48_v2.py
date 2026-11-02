from pathlib import Path
from collections import Counter
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
S = 48
P = {
    'ink':'#141C0B','rim':'#2A4111','rim2':'#3E6114','moss':'#2C510D',
    'deep':'#224B0D','shade':'#356E12','body':'#4C8D12','green':'#65A913',
    'green2':'#7FC019','lime':'#9FDC25','sun':'#BDE63A','glow':'#E5FA70',
    'white':'#F7FFD0','olive':'#687D24','slimeShade':'#566A18',
    'cavity':'#1F2412','cavity2':'#313119','mud':'#46371B','mud2':'#614A1E',
    'mud3':'#7B5B25','mudLight':'#A08738','eyeRim':'#31210B','eyeBurn':'#996612',
    'eye':'#F5C926','eyeLight':'#FFF1A6',
}

# Lower, heavier, more puddled silhouette. Symmetric outline only.
span = {
    8:(21,26), 9:(18,29), 10:(16,31), 11:(15,32), 12:(14,33), 13:(13,34),
    14:(12,35), 15:(11,36), 16:(10,37), 17:(9,38), 18:(8,39), 19:(8,39),
    20:(8,39), 21:(9,38), 22:(10,37), 23:(11,36), 24:(11,36), 25:(10,37),
    26:(9,38), 27:(8,39), 28:(7,40), 29:(6,41), 30:(5,42), 31:(4,43),
    32:(3,44), 33:(2,45), 34:(1,46), 35:(1,46), 36:(2,45), 37:(2,45),
    38:(3,44), 39:(5,42), 40:(7,40), 41:(10,37), 42:(13,34), 43:(17,30), 44:(20,27),
}
mask=Image.new('L',(S,S),0)
ma=ImageDraw.Draw(mask)
for y,(x0,x1) in span.items():
    ma.line((x0,y,x1,y), fill=255)
# mirrored side and base drips
for pts in [
    [(7,21),(6,22),(6,23),(5,24),(5,25),(5,26),(6,26),(6,27),(7,27),(8,28)],
    [(9,18),(8,19),(8,20),(9,20)],
    [(4,39),(4,40),(5,41),(6,42)],
    [(9,41),(9,42),(10,43)],
    [(14,43),(14,44)],
]:
    for x,y in pts:
        ma.point((x,y),255); ma.point((47-x,y),255)
# center hanging drops
for x,y in [(22,42),(22,43),(23,44),(24,44),(25,43),(25,42)]:
    ma.point((x,y),255)

base=Image.new('RGB',(S,S),P['body'])
d=ImageDraw.Draw(base)
def poly(x,c): d.polygon(x,fill=P[c])
def ell(x,c): d.ellipse(x,fill=P[c])
def ln(x,c,w=1): d.line(x,fill=P[c],width=w)
def pts(ps,c):
    for a,b in ps: d.point((a,b),fill=P[c])

# broad material planes: more puddled, layered lower mass
poly([(0,30),(9,28),(18,29),(24,31),(30,29),(39,28),(47,30),(47,47),(0,47)],'shade')
poly([(2,34),(8,31),(14,31),(18,34),(24,36),(30,33),(36,31),(43,33),(47,36),(47,47),(0,47),(0,36)],'green')
poly([(5,36),(11,33),(18,35),(24,37),(31,34),(39,35),(43,38),(40,41),(31,42),(16,42),(7,40)],'olive')
poly([(8,37),(14,35),(19,36),(24,38),(30,36),(36,36),(41,39),(39,42),(31,43),(16,43),(9,41)],'mud2')
poly([(10,39),(16,38),(23,39),(31,38),(38,39),(41,41),(36,43),(26,44),(14,43),(9,41)],'mud')

# central heavy sludge core, connected and flowing down
poly([(18,17),(22,15),(27,15),(31,17),(34,21),(33,24),(31,27),(32,30),(29,32),(24,33),(19,32),(16,30),(14,27),(15,23)],'moss')
poly([(19,19),(23,16),(27,16),(30,19),(30,23),(28,26),(29,29),(25,31),(20,30),(17,27),(17,23)],'deep')
poly([(20,20),(23,18),(26,18),(28,20),(28,23),(27,25),(26,28),(22,29),(19,27),(18,24)],'cavity2')
poly([(22,20),(25,20),(26,22),(25,24),(23,26),(21,24),(20,22)],'cavity')
# downward muddy stream under face
poly([(22,28),(24,28),(26,29),(27,31),(27,35),(24,38),(21,35),(21,31)],'mud2')
poly([(23,29),(25,29),(26,31),(25,34),(23,35),(22,32)],'mud3')

# upper translucent slime caps broken into patches, not a hat band
poly([(17,10),(22,8),(27,8),(31,10),(33,13),(32,16),(29,15),(25,13),(21,14),(17,13),(15,11)],'green2')
poly([(18,11),(21,9),(23,10),(22,12),(19,13),(17,12)],'lime')
poly([(25,9),(29,10),(30,12),(29,14),(26,13)],'green')
poly([(21,10),(23,9),(24,10),(23,11),(21,11)],'sun')
poly([(28,12),(30,13),(31,15),(29,16),(27,15)],'lime')

# heavier side masses and descending curtains of slime
poly([(10,16),(13,14),(16,15),(16,19),(13,21),(12,24),(10,26),(8,25),(8,20)],'green2')
poly([(31,15),(35,15),(38,18),(38,22),(36,25),(35,28),(33,27),(31,23),(31,19)],'green2')
poly([(10,17),(12,16),(12,18),(11,21),(9,23)],'lime')
poly([(35,17),(37,19),(36,22),(35,24)],'lime')
poly([(11,22),(12,22),(12,25),(11,27),(10,29),(9,29),(9,26)],'green')
poly([(35,22),(36,23),(36,27),(35,29),(34,30),(34,27)],'shade')
pts([(11,23),(11,24),(10,27),(36,24),(35,28)],'glow')

# lower puddle mounds and drippy rims
poly([(2,34),(5,33),(10,33),(12,35),(10,37),(5,37),(2,36)],'green2')
poly([(45,34),(42,33),(37,33),(35,35),(37,37),(43,37)],'green2')
poly([(8,39),(12,37),(18,38),(24,40),(30,38),(36,37),(40,39),(38,42),(30,43),(18,43),(10,42)],'green2')
poly([(16,39),(20,38),(24,39),(28,38),(32,39),(30,41),(24,42),(18,41)],'lime')
ln([(2,35),(4,34),(8,34),(10,35)],'lime')
ln([(37,34),(41,34),(45,35)],'lime')
ln([(9,40),(14,39),(17,40)],'sun')
ln([(31,40),(35,39),(39,40)],'sun')
pts([(5,34),(9,35),(40,35),(43,35),(16,40),(31,40),(24,41)],'glow')

# cavities and murky holes embedded in the sludge layers
for outline,inner in [
    ([(13,30),(17,29),(19,31),(18,34),(14,35),(11,33)],[(14,31),(17,30),(17,33),(14,33)]),
    ([(29,30),(33,29),(36,32),(34,35),(29,35),(27,32)],[(30,31),(33,31),(34,33),(30,34)]),
    ([(21,34),(25,33),(28,35),(27,38),(23,39),(19,37)],[(22,35),(25,35),(25,37),(22,38)]),
    ([(7,36),(11,35),(13,37),(11,39),(7,39)],[(8,36),(11,36),(11,38),(8,38)]),
    ([(35,36),(39,35),(42,37),(40,39),(35,39)],[(36,36),(39,36),(40,38),(36,38)]),
]:
    poly(outline,'mud3'); poly(inner,'cavity2')
pts([(16,31),(30,31),(24,35),(12,37),(37,37),(23,37)],'mudLight')
pts([(15,32),(31,32),(25,36),(11,38),(38,38)],'mud2')

# flowing internal streaks rather than costume-like bands
poly([(15,24),(17,23),(18,25),(18,29),(16,31),(14,30),(13,27)],'shade')
poly([(16,24),(17,24),(17,28),(16,30),(15,29)],'green2')
poly([(30,24),(32,25),(34,28),(34,31),(31,31),(29,29),(28,26)],'shade')
poly([(31,25),(33,28),(33,30),(31,30),(30,27)],'green')
poly([(19,31),(20,30),(22,31),(22,35),(20,36),(18,34)],'green')
poly([(26,31),(28,30),(30,31),(29,35),(27,36),(25,34)],'green2')

# pores and bubbles with brighter wet rims
for x,y,w,h in [(14,19,3,3),(32,18,2,4),(14,26,3,3),(31,26,3,2),(11,34,3,2),(31,34,3,3),(25,31,2,2),(20,12,2,2),(28,13,2,2)]:
    ell((x-1,y-1,x+w,y+h),'shade')
    ell((x,y,x+w-1,y+h-1),'cavity2')
    pts([(x,y)],'mud3')
# upper semi-buried holes
poly([(23,13),(25,12),(27,13),(27,16),(24,17),(22,15)],'shade')
poly([(24,13),(25,13),(26,14),(25,15),(24,15)],'mud')
poly([(17,16),(19,15),(20,16),(19,18),(17,18)],'shade')
pts([(18,16),(25,14)],'mud2')

# Eyes: sunken and less cute, still readable.
poly([(16,22),(19,21),(22,23),(22,26),(19,27),(16,25)],'eyeRim')
poly([(31,22),(28,21),(25,23),(25,26),(28,27),(31,25)],'eyeRim')
poly([(17,22),(19,22),(21,23),(21,25),(19,26),(17,24)],'eyeBurn')
poly([(30,22),(28,22),(26,23),(26,25),(28,26),(30,24)],'eyeBurn')
poly([(18,23),(20,24),(21,24),(20,25),(18,24)],'eye')
poly([(29,23),(27,24),(26,24),(27,25),(29,24)],'eye')
pts([(18,23),(29,23)],'eyeLight')
ln([(17,21),(20,21),(22,22)],'cavity')
ln([(30,21),(27,21),(25,22)],'cavity')
# dribble into face
poly([(23,17),(24,17),(24,19),(23,21),(22,20),(22,18)],'shade')
pts([(23,18),(23,19)],'green2')
pts([(23,28),(24,28)],'mud2')

# slimy film / highlights as patches and short arcs
for shp,col in [
    ([(18,10),(20,9),(22,10),(21,11),(18,11)],'glow'),
    ([(29,11),(31,12),(31,14),(29,14),(28,12)],'sun'),
    ([(10,17),(11,16),(12,18),(11,20),(10,19)],'sun'),
    ([(36,18),(37,20),(36,22),(35,21)],'sun'),
    ([(15,31),(16,30),(17,31),(16,33)],'lime'),
    ([(33,31),(34,32),(34,34),(33,34)],'lime'),
    ([(8,35),(10,34),(11,35),(9,36)],'sun'),
    ([(38,35),(40,34),(42,35),(40,36)],'sun'),
    ([(21,39),(24,38),(26,39),(24,40)],'sun'),
    ([(13,28),(14,27),(15,28),(14,29)],'lime'),
    ([(32,28),(33,29),(33,30),(32,30)],'lime'),
]:
    poly(shp,col)
pts([(19,10),(30,12),(11,17),(36,19),(16,31),(34,32),(9,35),(40,35),(23,39)],'white')
# scattered trapped pockets
for x,y in [(18,13),(30,14),(12,18),(34,18),(13,26),(36,24),(9,31),(37,31),(19,37),(30,38)]:
    d.point((x,y),fill=P['green'])
    d.point((x,y-1),fill=P['sun'])
# larger bubbles
for (x,y,r) in [(31,15,2),(35,35,2),(15,38,2),(10,24,2)]:
    ell((x-r,y-r,x+r,y+r),'shade')
    ell((x-r+1,y-r+1,x+r-1,y+r-1),'green2')
    pts([(x-1,y-1)],'white')

# Composite with black outer rim and olive near-rim
result=Image.new('RGBA',(S,S),(0,0,0,0))
source=base.load(); m=mask.load(); out=result.load()
for y in range(S):
    for x in range(S):
        if not m[x,y]:
            continue
        neighbors=[(x-1,y),(x+1,y),(x,y-1),(x,y+1)]
        edge=any(nx<0 or nx>=S or ny<0 or ny>=S or not m[nx,ny] for nx,ny in neighbors)
        if edge:
            col=P['ink']
        else:
            near=any(any(xx<0 or xx>=S or yy<0 or yy>=S or not m[xx,yy]
                         for xx,yy in [(nx-1,ny),(nx+1,ny),(nx,ny-1),(nx,ny+1)])
                     for nx,ny in neighbors if 0<=nx<S and 0<=ny<S and m[nx,ny])
            col=P['rim2' if y<24 else 'rim'] if near else None
        if col is not None:
            out[x,y]=tuple(bytes.fromhex(col[1:]))+(255,)
        else:
            out[x,y]=source[x,y]+(255,)

# mirrored outer droplets / ooze beads
rd=ImageDraw.Draw(result)
for x,y in [(4,40),(8,18),(7,23)]:
    for xx in (x,47-x):
        rd.point((xx,y),fill=P['sun'])
        if y+1<S:
            rd.point((xx,y+1),fill=P['green'])

assert all(bool(out[x,y][3])==bool(out[S-1-x,y][3]) for y in range(S) for x in range(S//2))
palette={px for px,n in Counter(result.get_flattened_data()).items() if px[3]}
result.save(HERE/'hedoro_puddle_48_v2.png', optimize=True)
result.resize((S*12,S*12),Image.Resampling.NEAREST).save(HERE/'hedoro_puddle_48_v2_zoom.png', optimize=True)
# comparison preview
W,H=780,690
preview=Image.new('RGB',(W,H),'#131924'); pv=ImageDraw.Draw(preview)
zoom=result.resize((576,576),Image.Resampling.NEAREST)
for y in range(30,606,24):
    for x in range(22,598,24):
        pv.rectangle((x,y,x+23,y+23), fill='#263747' if ((x-22)//24 + (y-30)//24)%2 else '#20313F')
preview.paste(zoom,(22,30),zoom)
pv.rectangle((630,80,697,147),fill='#243645')
preview.paste(result,(640,90),result)
pv.text((22,9),'48 x 48 px / sludge-heavy revision / enlarged 12x',fill='#E8F2EC')
pv.text((626,58),'Native 1x',fill='#E8F2EC')
pv.text((625,161),f'{len(palette)} colors',fill='#AEC3BA')
pv.text((23,618),'Heavier lower mass / more drips / denser muddy layers / slimy film highlights',fill='#D6E5DD')
preview.save(HERE/'hedoro_puddle_48_v2_preview.png', optimize=True)
print('DONE', len(palette), 'colors')