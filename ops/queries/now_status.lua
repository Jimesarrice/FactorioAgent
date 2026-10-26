local p = game.connected_players[1]
if not p then return "no-player" end
local inv = p.get_main_inventory()
local out = {}
for _, s in pairs(inv.get_contents()) do out[#out+1] = s.name .. "=" .. s.count end
table.sort(out)
local stats = game.forces.player.get_item_production_statistics(p.surface)
return "pos=" .. math.floor(p.position.x) .. "," .. math.floor(p.position.y)
  .. " speed=" .. game.speed
  .. " inv={" .. table.concat(out, ",") .. "}"
  .. " iron_plates_total=" .. stats.get_output_count("iron-plate")
