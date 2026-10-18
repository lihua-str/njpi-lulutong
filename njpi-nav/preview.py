from PIL import Image
img = Image.open(r"D:\IMG_20261018_222221.png")
print("original:", img.size)
img.thumbnail((1600, 1600))
out = r"C:\Users\郭凡\Doubao\chats\2026-10-18\new-chat\njpi-nav\_orig_map_preview.png"
img.save(out)
print("saved:", out, img.size)
