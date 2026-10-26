local s=game.surfaces.nauvis
local step=8
local x0,y0=-1100,-1100
local x1,y1=1100,1100
local nx=math.floor((x1-x0)/step)+1
local ny=math.floor((y1-y0)/step)+1
local land={}
local function idx(ix,iy) return iy*nx+ix end
local function ok(ix,iy)
  local k=idx(ix,iy)
  if land[k]~=nil then return land[k] end
  local x,y=x0+ix*step,y0+iy*step
  local t=s.get_tile(x,y)
  local v=t and t.name~="water" and t.name~="deepwater"
  land[k]=v
  return v
end
local comp={}
local sizes={}
local cid=0
for iy=0,ny-1 do
  for ix=0,nx-1 do
    local k=idx(ix,iy)
    if comp[k]==nil and ok(ix,iy) then
      cid=cid+1
      local q,head={k},1
      comp[k]=cid
      local n=0
      while head<=#q do
        local cur=q[head]; head=head+1; n=n+1
        local cy=math.floor(cur/nx); local cx=cur-cy*nx
        for dx=-1,1 do for dy=-1,1 do
          if dx~=0 or dy~=0 then
            local nxx,nyy=cx+dx,cy+dy
            if nxx>=0 and nyy>=0 and nxx<nx and nyy<ny then
              local k2=idx(nxx,nyy)
              if comp[k2]==nil and ok(nxx,nyy) then comp[k2]=cid; q[#q+1]=k2 end
            end
          end
        end end
      end
      sizes[cid]=n
    end
  end
end
local function cell(x,y) return math.floor((x-x0)/step+0.5),math.floor((y-y0)/step+0.5) end
local bx,by=cell(-43,43)
local ox,oy=cell(-415,-872)
local bc,oc=comp[idx(bx,by)],comp[idx(ox,oy)]
local out={string.format("components=%d base_comp=%s oil_comp=%s base_size=%s oil_size=%s",cid,tostring(bc),tostring(oc),tostring(sizes[bc]),tostring(sizes[oc]))}
local blist,olist={},{}
for iy=0,ny-1 do
  for ix=0,nx-1 do
    local k=idx(ix,iy)
    if comp[k]==bc then blist[#blist+1]={x=x0+ix*step,y=y0+iy*step}
    elseif comp[k]==oc then olist[#olist+1]={x=x0+ix*step,y=y0+iy*step} end
  end
end
local bestd,besta,bestb
for _,a in ipairs(blist) do
  for _,b in ipairs(olist) do
    local dx,dy=a.x-b.x,a.y-b.y
    local d=dx*dx+dy*dy
    if not bestd or d<bestd then bestd=d; besta=a; bestb=b end
  end
end
if besta then
  out[#out+1]=string.format("closest base=(%.0f,%.0f) oil=(%.0f,%.0f) gap=%.0f tiles",besta.x,besta.y,bestb.x,bestb.y,math.sqrt(bestd))
end
return table.concat(out,"\n")
