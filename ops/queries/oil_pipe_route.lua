local s=game.surfaces.nauvis
local out={}
local bad={}
-- horizontal y=428.5 from x=353.5 down to 301.5
for x=302,353 do
  if not s.can_place_entity{name="pipe",position={x=x+0.5,y=428.5},force=game.forces.player} then bad[#bad+1]="H"..x end
end
-- vertical x=301.5 from y=428.5 to 416.5
for y=417,427 do
  if not s.can_place_entity{name="pipe",position={x=301.5,y=y+0.5},force=game.forces.player} then bad[#bad+1]="V"..y end
end
-- power poles route x=296.5? list candidates
local poles={}
for y=438,414,-6 do
  if s.can_place_entity{name="small-electric-pole",position={x=297.5,y=y+0.5},force=game.forces.player} then poles[#poles+1]=y end
end
return "bad="..table.concat(bad,",").."|poles="..table.concat(poles,",")