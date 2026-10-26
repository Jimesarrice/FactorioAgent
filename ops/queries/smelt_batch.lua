local s=game.surfaces.nauvis
local p=game.players["LLM-Bot"]
local inv=p.get_main_inventory()
local byid={}
for _,e in pairs(s.find_entities_filtered{force="player"}) do
  if e.unit_number then byid[e.unit_number]=e end
end
local out={}
-- fuel boilers 5 coal each
local bc=0
for _,u in ipairs({36,125,128,131}) do
  local e=byid[u]
  if e then
    local n=e.insert({name="coal",count=5}); if n and n>0 then inv.remove({name="coal",count=n}); bc=bc+n end
  end
end
out[#out+1]="boiler_coal="..bc
-- chests
local iro=byid[204]
local cuo=byid[214]
local function chest_take(chest,name,want)
  if not chest then return 0 end
  local n=0
  for i=1,3 do
    local ci=chest.get_inventory(i)
    if ci and n<want then
      local take=math.min(ci.get_item_count(name),want-n)
      if take>0 then local rm=ci.remove({name=name,count=take}); n=n+rm end
    end
  end
  return n
end
local iron_furnaces={161,162,163,164,165,166,167,168}
local cu_furnaces={171,172}
local loaded_iron,loaded_cu=0,0
for _,u in ipairs(iron_furnaces) do
  local e=byid[u]
  if e then
    local ore=chest_take(iro,"iron-ore",36)
    local a=e.insert({name="iron-ore",count=ore}); loaded_iron=loaded_iron+(a or 0)
    local c=e.insert({name="coal",count=20}); if c and c>0 then inv.remove({name="coal",count=c}) end
  end
end
for _,u in ipairs(cu_furnaces) do
  local e=byid[u]
  if e then
    local ore=chest_take(cuo,"copper-ore",59)
    local a=e.insert({name="copper-ore",count=ore}); loaded_cu=loaded_cu+(a or 0)
    local c=e.insert({name="coal",count=20}); if c and c>0 then inv.remove({name="coal",count=c}) end
  end
end
out[#out+1]="loaded_iron="..loaded_iron.." loaded_copper="..loaded_cu.." coal_left="..inv.get_item_count("coal")
return table.concat(out,"\n")
