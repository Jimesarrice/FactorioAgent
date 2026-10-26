local s=game.surfaces.nauvis
local x0,y0,x1,y1=180,240,330,460
local nx=x1-x0+1
local ny=y1-y0+1
local function idx(x,y) return (y-y0)*nx+(x-x0) end
local cache={}
local function iswater(x,y)
  local k=idx(x,y)
  if cache[k]~=nil then return cache[k] end
  local ok,t=pcall(function() return s.get_tile(x,y) end)
  local v=not (ok and t and t.valid and t.name~="water" and t.name~="deepwater")
  cache[k]=v
  return v
end
local function nearest_land(x,y)
  for r=0,20 do
    for dx=-r,r do for dy=-r,r do
      if math.abs(dx)==r or math.abs(dy)==r then
        local xx,yy=x+dx,y+dy
        if xx>=x0 and xx<=x1 and yy>=y0 and yy<=y1 and not iswater(xx,yy) then return xx,yy end
      end
    end end
  end
end
local sx,sy=nearest_land(220,280)
local tx,ty=nearest_land(276,408)
if not sx or not tx then return "no land endpoints" end
-- 0-1 BFS (deque implemented as two tables)
local dist={} local prev={}
local q={ {sx,sy} }
dist[idx(sx,sy)]=0
local head=1
while head<=#q do
  local cur=q[head]; head=head+1
  local x,y=cur[1],cur[2]
  local d=dist[idx(x,y)]
  for _,dd in ipairs({{1,0},{-1,0},{0,1},{0,-1}}) do
    local xx,yy=x+dd[1],y+dd[2]
    if xx>=x0 and xx<=x1 and yy>=y0 and yy<=y1 then
      local w=iswater(xx,yy) and 1 or 0
      local nd=d+w
      local k=idx(xx,yy)
      if dist[k]==nil or nd<dist[k] then
        dist[k]=nd; prev[k]={x,y}
        if w==0 then table.insert(q,head,{xx,yy}) else q[#q+1]={xx,yy} end
      end
    end
  end
end
local target=idx(tx,ty)
if dist[target]==nil then return "no path" end
-- reconstruct number of water tiles
local water=0; local length=0
local waters={}
local cx,cy=tx,ty
while not (cx==sx and cy==sy) do
  length=length+1
  if iswater(cx,cy) then water=water+1; table.insert(waters,1,cx..","..cy) end
  local p=prev[idx(cx,cy)]
  if not p then break end
  cx,cy=p[1],p[2]
end
return string.format("start=(%d,%d) end=(%d,%d) path_tiles=%d water_tiles=%d%s%s",sx,sy,tx,ty,length,water,"\n",table.concat(waters," "))
