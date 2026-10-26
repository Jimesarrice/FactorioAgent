local s=game.surfaces.nauvis
local p=game.players["LLM-Bot"]
local inv=p.get_main_inventory()
local byid={}
for _,e in pairs(s.find_entities_filtered{force="player"}) do if e.unit_number then byid[e.unit_number]=e end end
local targets={
 {217,10},{218,10},{219,10},
 {36,10},{125,10},{128,10},{131,10},
 {181,10},{182,10},{183,10},{184,10},{185,10},
 {203,10},
}
local out={}
for _,t in ipairs(targets) do
  local e=byid[t[1]]
  if e then
    local n=e.insert({name="coal",count=t[2]})
    if n and n>0 then inv.remove({name="coal",count=n}); out[#out+1]=t[1]..":"..n end
  end
end
return "fueled="..table.concat(out,",").." coal_left="..inv.get_item_count("coal")
