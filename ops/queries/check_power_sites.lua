local s=game.surfaces.nauvis
local clusters={
 {pump={55.5,34.5}, boiler={51.5,34}, engine={51.5,30.5}},
 {pump={55.5,42.5}, boiler={51.5,42}, engine={51.5,38.5}},
 {pump={55.5,18.5}, boiler={51.5,18}, engine={51.5,14.5}},
}
local out={}
local function water_count(x,y)
  local c=0
  for ox=-0.5,0.5,1 do for oy=-0.5,0.5,1 do
    local t=s.get_tile(x+ox,y+oy)
    if t and (t.name=="water" or t.name=="deepwater") then c=c+1 end
  end end
  return c
end
for i,c in ipairs(clusters) do
  local px,py=c.pump[1],c.pump[2]
  local ok=s.can_place_entity{name="offshore-pump",position={x=px,y=py},direction=4,force=game.forces.player}
  local okb=s.can_place_entity{name="boiler",position={x=c.boiler[1],y=c.boiler[2]},direction=0,force=game.forces.player}
  local oke=s.can_place_entity{name="steam-engine",position={x=c.engine[1],y=c.engine[2]},direction=0,force=game.forces.player}
  out[#out+1]=string.format("cluster%d pump=(%.1f,%.1f) water=%d can=%s boiler can=%s engine can=%s",i,px,py,water_count(px,py),tostring(ok),tostring(okb),tostring(oke))
end
return table.concat(out,"\n")
