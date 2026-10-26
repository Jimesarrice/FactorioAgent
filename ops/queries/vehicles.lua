local s=game.surfaces.nauvis
local t={}
for _,e in pairs(s.find_entities_filtered{type={"car","tank","locomotive","cargo-wagon","spider-vehicle"}}) do
  t[#t+1]=string.format("%s#%s @(%.1f,%.1f)",e.name,tostring(e.unit_number),e.position.x,e.position.y)
end
return table.concat(t,"\n")
