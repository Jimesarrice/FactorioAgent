local s=game.surfaces.nauvis
local step=8
local x0,y0=-100,0
local x1,y1=700,700
local nx=math.floor((x1-x0)/step)+1
local ny=math.floor((y1-y0)/step)+1
local okcache={}
local function idx(ix,iy) return iy*nx+ix end
local function tile_ok(ix,iy)
  local k=idx(ix,iy)
  if okcache[k]~=nil then return okcache[k] end
  local x,y=x0+ix*step,y0+iy*step
  local t=s.get_tile(x,y)
  local ok=t and t.name~="water" and t.name~="deepwater"
  okcache[k]=ok
  return ok
end
local function tocell(x,y) return math.floor((x-x0)/step+0.5), math.floor((y-y0)/step+0.5) end
local sx,sy=tocell(-10,55)
local ex,ey=tocell(350,435)
local q,head={},1
local prev={}
prev[idx(sx,sy)]=-1
q[1]=idx(sx,sy)
local found=false
while head<=#q do
  local cur=q[head]; head=head+1
  local cy=math.floor(cur/nx); local cx=cur-cy*nx
  if cx==ex and cy==ey then found=true break end
  for dx=-1,1 do
    for dy=-1,1 do
      if dx~=0 or dy~=0 then
        local nxx,nyy=cx+dx,cy+dy
        if nxx>=0 and nyy>=0 and nxx<nx and nyy<ny then
          local k=idx(nxx,nyy)
          if prev[k]==nil and tile_ok(nxx,nyy) then
            prev[k]=cur; q[#q+1]=k
          end
        end
      end
    end
  end
end
if not found then return "no path; visited="..#q end
local path={}
local cur=idx(ex,ey)
while cur~=-1 do
  local cy=math.floor(cur/nx); local cx=cur-cy*nx
  table.insert(path,1,{x=x0+cx*step+0.5,y=y0+cy*step+0.5})
  cur=prev[cur]
end
local parts={}
for _,p in ipairs(path) do parts[#parts+1]=string.format("(%.0f,%.0f)",p.x,p.y) end
return "path points="..#path.."\n"..table.concat(parts," ")
