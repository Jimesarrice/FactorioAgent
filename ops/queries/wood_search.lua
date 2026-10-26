local s=game.surfaces.nauvis
local t={}
for _,e in pairs(s.find_entities_filtered{type="container",force="player"}) do
  local maxi=(e.get_max_inventory_index and e.get_max_inventory_index()) or 1
  for i=1,maxi do local inv=e.get_inventory(i) if inv then local n=inv.get_item_count("wood") if n>0 then t[#t+1]=string.format("#%s @(%.1f,%.1f) wood=%d",tostring(e.unit_number),e.position.x,e.position.y,n) end end end
end
-- nearest trees
local p=game.connected_players[1]
local trees=s.find_entities_filtered{position=p.position,radius=200,type="tree"}
table.sort(trees,function(a,b) return (a.position.x-p.position.x)^2+(a.position.y-p.position.y)^2 < (b.position.x-p.position.x)^2+(b.position.y-p.position.y)^2 end)
for i=1,math.min(5,#trees) do local e=trees[i]; t[#t+1]=string.format("tree @(%.1f,%.1f) dist=%.1f",e.position.x,e.position.y,math.sqrt((e.position.x-p.position.x)^2+(e.position.y-p.position.y)^2)) end
return table.concat(t,"\n")
