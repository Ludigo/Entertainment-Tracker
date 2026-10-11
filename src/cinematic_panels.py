"""Rounded content panels share document coordinates with their text."""
from PIL import Image,ImageDraw,ImageTk

def draw_panels(canvas,boxes):
    photos=[]
    for x0,y0,x1,y1 in boxes:
        width=max(1,round(x1-x0));height=max(1,round(y1-y0))
        image=Image.new('RGBA',(width,height),(0,0,0,0))
        draw=ImageDraw.Draw(image)
        draw.rounded_rectangle((0,0,width-1,height-1),radius=12,
                              fill=(13,16,22,210),outline=(88,96,109,110))
        photo=ImageTk.PhotoImage(image);photos.append(photo)
        ident=canvas.create_image(x0,y0,image=photo,anchor='nw',tags='paint')
        canvas.tag_lower(ident)
    return photos
