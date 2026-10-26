local s=game.surfaces.nauvis
local p=game.players["LLM-Bot"]
local inv=p.get_main_inventory()
local byid={}
for _,e in pairs(s.find_entities_filtered{force="player"}) do
  if e.unit_number then byid[e.unit_number]=e end
end
local chest=byid[204]
local function take(name,want)
  if not chest then return 0 end
  local n=0
  for i=1,3 do
    local ci=chest.get_inventory(i)
    if ci and n<want then
      local t=math.min(ci.get_item_count(name),want-n)
      if t>0 then
        local rm=ci.remove({name=name,count=t})
        n=n+rm
      end
    end
  end
  return n
end
local loaded=0
for _,u in ipairs({161,162,163,164}) do
  local e=byid[u]
  if e then
    local ore=take("iron-ore",70)
    loaded=loaded+(e.insert({name="iron-ore",count=ore}) or 0)
    local c=e.insert({name="coal",count=6})
    if c and c>0 then inv.remove({name="coal",count=c}) end
  end
end
return "loaded="..loaded.." coal_left="..inv.get_item_count("coal")
