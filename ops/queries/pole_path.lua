local s=game.surfaces.nauvis
local x0,y0,x1,y1=288,426,358,458
local cache={}
local function idx(x,y) return (y-y0)*(x1-x0+1)+(x-x0) end
local function ok(x,y)
  local k=idx(x,y)
  if cache[k]~=nil then return cache[k] end
  local v=s.can_place_entity{name="small-electric-pole",position={x=x+0.5,y=y+0.5},force=game.forces.player}
  cache[k]=v
  return v
end
local function cell(x,y) return math.floor(x-0.5),math.floor(y-0.5) end
local sx,sy=cell(296.5,445.5)
local tx,ty=cell(351.5,435.5)
local q,head,prev={},1,{}
prev[idx(sx,sy)]=-1
q[1]=idx(sx,sy)
local found=false
while head<=#q do
  local cur=q[head]; head=head+1
  local cy=math.floor(cur/(x1-x0+1))+y0; local cx=cur-(cy-y0)*(x1-x0+1)+x0
  if cx==tx and cy==ty then found=true break end
  for dx=-7,7 do for dy=-7,7 do
    if dx~=0 or dy~=0 then
      local d=math.sqrt(dx*dx+dy*dy)
      if d<=7.5 then
        local nx,ny=cx+dx,cy+dy
        if nx>=x0 and nx<=x1 and ny>=y0 and ny<=y1 and ok(nx,ny) then
          local k=idx(nx,ny)
          if prev[k]==nil then prev[k]=cur; q[#q+1]=k end
        end
      end
    end
  end end
end
if not found then return "no pole path" end
local path={}
local cur=idx(tx,ty)
while cur~=-1 do
  local cy=math.floor(cur/(x1-x0+1))+y0; local cx=cur-(cy-y0)*(x1-x0+1)+x0
  table.insert(path,1,string.format("%.1f,%.1f",cx+0.5,cy+0.5))
  cur=prev[cur]
end
return #path.."\n"..table.concat(path," ")
