local s=game.surfaces.nauvis
local t={}
for _,p in ipairs({{-48.5,60.5},{-43.5,60.5}}) do
  local e=s.find_entity("underground-belt",{p[1],p[2]})
  local b=e.belt_neighbours
  local function q(side)
    if not b[side] then return "nil" end
    local n=b[side]
    return string.format("%s@%.1f,%.1f",n.name,n.position.x,n.position.y)
  end
  t[#t+1]=string.format("%.1f,%.1f left=%s right=%s",p[1],p[2],q("left"),q("right"))
end
return table.concat(t,"\n")
