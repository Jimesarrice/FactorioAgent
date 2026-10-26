local s=game.surfaces.nauvis
local out={}
local function water_count(x,y)
  local c=0
  for ox=-0.5,0.5,1 do for oy=-0.5,0.5,1 do
    local t=s.get_tile(x+ox,y+oy)
    if t and (t.name=="water" or t.name=="deepwater") then c=c+1 end
  end end
  return c
end
for y=10,44 do
  for x=50,60 do
    local px,py=x+0.5,y+0.5
    if water_count(px,py)>=2 and s.can_place_entity{name="offshore-pump",position={x=px,y=py},direction=4,force=game.forces.player} then
      local bx,by=px-4,py-0.5
      local ex,ey=bx,by-3.5
      local okb=s.can_place_entity{name="boiler",position={x=bx,y=by},direction=0,force=game.forces.player}
      local oke=s.can_place_entity{name="steam-engine",position={x=ex,y=ey},direction=0,force=game.forces.player}
      if okb and oke then
        out[#out+1]=string.format("pump=(%.1f,%.1f) water=%d boiler=(%.1f,%.1f) engine=(%.1f,%.1f)",px,py,water_count(px,py),bx,by,ex,ey)
      end
    end
  end
end
return table.concat(out,"\n")
