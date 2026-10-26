local s=game.surfaces.nauvis
local p=game.players["LLM-Bot"]
local inv=p.get_main_inventory()
local byid={}
for _,e in pairs(s.find_entities_filtered{force="player"}) do if e.unit_number then byid[e.unit_number]=e end end
local ids={161,162,163,164,165,166,167,168,169,170,171,172}
local loaded,coal=0,0
for _,u in ipairs(ids) do
  local e=byid[u]
  if e then
    local ore=e.insert({name="iron-ore",count=25})
    if ore and ore>0 then inv.remove({name="iron-ore",count=ore}); loaded=loaded+ore end
    local c=e.insert({name="coal",count=4})
    if c and c>0 then inv.remove({name="coal",count=c}); coal=coal+c end
  end
end
return "loaded="..loaded.." coal_used="..coal.." coal_left="..inv.get_item_count("coal").." ore_left="..inv.get_item_count("iron-ore")
