local s=game.surfaces.nauvis
local rows={}
for y=405,430 do
  local row=""
  for x=295,315 do
    local ok=s.can_place_entity{name="pipe",position={x=x+0.5,y=y+0.5},force=game.forces.player}
    local tile=s.get_tile(x+0.5,y+0.5)
    local ch="."
    if not ok then
      if tile and (tile.name=="water" or tile.name=="deepwater" or tile.name=="water-shallow" or tile.name=="water-mud") then ch="~" else ch="#" end
    end
    row=row..ch
  end
  rows[#rows+1]=string.format("%d %s",y,row)
end
return table.concat(rows,"\n")
