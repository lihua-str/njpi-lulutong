from PIL import Image
import collections

img = Image.open(r"C:\Users\郭凡\Doubao\chats\2026-10-18\new-chat\njpi-nav\assets\logo.png").convert("RGBA")
w, h = img.size
px = img.load()

# 白色阈值
def is_white(r, g, b):
    return r > 235 and g > 235 and b > 235

# 从四角开始 flood fill 白色背景
visited = [[False]*h for _ in range(w)]
queue = collections.deque()

# 四个角附近作为种子点
seeds = [(0,0), (w-1,0), (0,h-1), (w-1,h-1),
         (w//2, 0), (w//2, h-1), (0, h//2), (w-1, h//2)]
for sx, sy in seeds:
    r,g,b,a = px[sx,sy]
    if is_white(r,g,b):
        queue.append((sx,sy))
        visited[sx][sy] = True

while queue:
    x, y = queue.popleft()
    r,g,b,a = px[x,y]
    px[x,y] = (r,g,b,0)
    for dx,dy in [(-1,0),(1,0),(0,-1),(0,1)]:
        nx, ny = x+dx, y+dy
        if 0 <= nx < w and 0 <= ny < h and not visited[nx][ny]:
            nr,ng,nb,na = px[nx,ny]
            if is_white(nr,ng,nb):
                visited[nx][ny] = True
                queue.append((nx,ny))

out = r"C:\Users\郭凡\Doubao\chats\2026-10-18\new-chat\njpi-nav\assets\logo_t.png"
img.save(out)
print("saved:", out, img.size)
