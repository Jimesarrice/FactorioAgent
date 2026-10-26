local s=game.surfaces.nauvis
local t={}
for _,e in pairs(s.find_entities_filtered{area={{290,408},{360,440}},type="pipe"}) do
  local ok,c=pcall(function() return e.get_fluid_contents() end)
  if ok and c and c["crude-oil"] and c["crude-oil"]>0 then
    t[#t+1]=string.format("%.1f,%.1f",e.position.x,e.position.y)
  end
end
return table.concat(t," ")
