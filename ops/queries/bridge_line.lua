local s=game.surfaces.nauvis
local ax,ay,bx,by=220,280,276,408
-- extend the line to find land on both ends
local dx,dy=bx-ax,by-ay
local len=math.sqrt(dx*dx+dy*dy)
local ux,uy=dx/len,dy/len
local function tile(x,y)
  local ok,t=pcall(function() return s.get_tile(math.floor(x),math.floor(y)) end)
  if not ok or not t or not t.valid then return nil end
  return t
end
local function iswater(t) return t and (t.name=="water" or t.name=="deepwater") end
local startx,starty=ax-ux*30,ay-uy*30
local endx,endy=bx+ux*30,by+uy*30
local L=math.sqrt((endx-startx)^2+(endy-starty)^2)
local n=math.floor(L)+1
local waters={}
local firstwater,lastwater
for i=0,n do
  local x=startx+ux*i
  local y=starty+uy*i
  local t=tile(x,y)
  if iswater(t) then
    waters[#waters+1]=string.format("%.1f,%.1f",math.floor(x)+0.5,math.floor(y)+0.5)
    if not firstwater then firstwater=i end
    lastwater=i
  end
end
return string.format("len=%.0f samples=%d water=%d first=%s last=%s\n%s",L,n,#waters,tostring(firstwater),tostring(lastwater),table.concat(waters," "))
