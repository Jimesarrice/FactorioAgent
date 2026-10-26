local s=game.surfaces.nauvis
local p=game.players["LLM-Bot"]
local inv=p.get_main_inventory()
local ids={181,182,183,184,185,186}
local byid={}
for _,e in pairs(s.find_entities_filtered{type="mining-drill",force="player"}) do
  byid[e.unit_number]=e
end
local moved=0
for _,u in ipairs(ids) do
  local e=byid[u]
  if e then
    local n=e.insert({name="coal",count=20})
    if n and n>0 then inv.remove({name="coal",count=n}); moved=moved+n end
  end
end
return "fueled="..moved.." coal_left="..inv.get_item_count("coal")
