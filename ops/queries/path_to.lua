local s=game.surfaces.nauvis
local step=4
local sx,sy=-59,43
local tx,ty=220,280
local x0,y0=math.min(sx,tx)-50,math.min(sy,ty)-50
local x1,y1=math.max(sx,tx)+50,math.max(sy,ty)+50
local nx=math.floor((x1-x0)/step)+1
local ny=math.floor((y1-y0)/step)+1
local cache={}
local function idx(ix,iy) return iy*nx+ix end
local function ok(ix,iy)
  local k=idx(ix,iy)
  if cache[k]~=nil then return cache[k] end
  local x,y=x0+ix*step,y0+iy*step
  local okt,t=pcall(function() return s.get_tile(x,y) end)
  local v=okt and t and t.valid and t.name~="water" and t.name~="deepwater"
  if v then
    local cliffs=#s.find_entities_filtered{area={{x-1,y-1},{x+1,y+1}},type="cliff"}
    if cliffs>0 then v=false end
  end
  cache[k]=v
  return v
end
local function cell(x,y) return math.floor((x-x0)/step+0.5),math.floor((y-y0)/step+0.5) end
local scx,scy=cell(sx,sy)
local tcx,tcy=cell(tx,ty)
local q,head,prev={},1,{}
prev[idx(scx,scy)]=-1
q[1]=idx(scx,scy)
local found=false
while head<=#q do
  local cur=q[head]; head=head+1
  local cy=math.floor(cur/nx); local cx=cur-cy*nx
  if cx==tcx and cy==tcy then found=true break end
  for dx=-1,1 do for dy=-1,1 do
    if dx~=0 or dy~=0 then
      local ax,ay=cx+dx,cy+dy
      if ax>=0 and ay>=0 and ax<nx and ay<ny then
        local k=idx(ax,ay)
        if prev[k]==nil and ok(ax,ay) then prev[k]=cur; q[#q+1]=k end
      end
    end
  end end
end
if not found then return "no path visited="..#q end
local path={}
local cur=idx(tcx,tcy)
while cur~=-1 do
  local cy=math.floor(cur/nx); local cx=cur-cy*nx
  table.insert(path,1,string.format("(%.0f,%.0f)",x0+cx*step,y0+cy*step))
  cur=prev[cur]
end
return "pts="..#path.."\n"..table.concat(path," ")
