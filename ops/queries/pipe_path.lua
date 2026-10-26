local s=game.surfaces.nauvis
local sx,sy=353.5,428.5
local tx,ty=301.5,416.5
local x0,y0,x1,y1=295,405,358,435
local nx=x1-x0+1
local ny=y1-y0+1
local cache={}
local function idx(ix,iy) return iy*nx+ix end
local function ix(x) return math.floor(x)-x0 end
local function iy(y) return math.floor(y)-y0 end
local function ok(ixx,iyy)
  local k=idx(ixx,iyy)
  if cache[k]~=nil then return cache[k] end
  local x,y=x0+ixx,y0+iyy
  local v=s.can_place_entity{name="pipe",position={x=x+0.5,y=y+0.5},force=game.forces.player}
  cache[k]=v
  return v
end
local startx,starty=ix(sx),iy(sy)
local endx,endy=ix(tx),iy(ty)
local q,head,prev={},1,{}
prev[idx(startx,starty)]=-1
q[1]=idx(startx,starty)
local found=false
while head<=#q do
  local cur=q[head]; head=head+1
  local cy=math.floor(cur/nx); local cx=cur-cy*nx
  if cx==endx and cy==endy then found=true break end
  for _,dd in ipairs({{1,0},{-1,0},{0,1},{0,-1}}) do
    local ax,ay=cx+dd[1],cy+dd[2]
    if ax>=0 and ay>=0 and ax<nx and ay<ny then
      local k=idx(ax,ay)
      if prev[k]==nil and ok(ax,ay) then prev[k]=cur; q[#q+1]=k end
    end
  end
end
if not found then return "no path visited="..#q end
local path={}
local cur=idx(endx,endy)
while cur~=-1 do
  local cy=math.floor(cur/nx); local cx=cur-cy*nx
  table.insert(path,1,string.format("%.1f,%.1f",x0+cx+0.5,y0+cy+0.5))
  cur=prev[cur]
end
return "path="..#path.."\n"..table.concat(path," ")
