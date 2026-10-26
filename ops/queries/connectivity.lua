local s=game.surfaces.nauvis
local step=8
local x0,y0,x1,y1=-850,-800,850,880
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
  cache[k]=v
  return v
end
local function cell(x,y) return math.floor((x-x0)/step+0.5),math.floor((y-y0)/step+0.5) end
local sx,sy=cell(-43,43)
local function path_to(tx,ty)
  local tcx,tcy=cell(tx,ty)
  local q,head,prev={},1,{}
  prev[idx(sx,sy)]=-1; q[1]=idx(sx,sy)
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
  if not found then return nil,#q end
  local n=0; local cur=idx(tcx,tcy)
  while cur~=-1 do n=n+1; cur=prev[cur] end
  return n,#q
end
local out={}
for _,t in ipairs({{-40,-730},{222,-730},{-300,-730},{790,56},{790,240},{790,712},{-198,820},{-724,820}}) do
  local n,vis=path_to(t[1],t[2])
  out[#out+1]=string.format("target %d,%d -> %s visited=%d",t[1],t[2],n and ("path="..n) or "NO PATH",vis)
end
return table.concat(out,"\n")
