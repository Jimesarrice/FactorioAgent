local s=game.surfaces.nauvis
local out={}
local function land(x,y)
  local ok,t=pcall(function() return s.get_tile(x,y) end)
  if not ok or not t or not t.valid then return false end
  local n=t.name
  return n~="water" and n~="deepwater"
end
local function scan_side(name, fixed, axis, from, to)
  local runs={}
  local start=nil
  for v=from,to,4 do
    local x,y
    if axis=="x" then x=v; y=fixed else x=fixed; y=v end
    if land(x,y) then
      if not start then start=v end
    else
      if start then runs[#runs+1]={start,v-4} start=nil end
    end
  end
  if start then runs[#runs+1]={start,to} end
  table.sort(runs,function(a,b) return (b[2]-b[1])>(a[2]-a[1]) end)
  for i=1,math.min(3,#runs) do
    local r=runs[i]
    local mid=(r[1]+r[2])/2
    local x,y
    if axis=="x" then x=mid; y=fixed else x=fixed; y=mid end
    out[#out+1]=string.format("%s run %d..%d mid=(%.0f,%.0f) len=%d",name,r[1],r[2],x,y,r[2]-r[1])
  end
end
scan_side("north",-730,"x",-790,790)
scan_side("south",820,"x",-790,790)
scan_side("west",-790,"y",-730,820)
scan_side("east",790,"y",-730,820)
return table.concat(out,"\n")
