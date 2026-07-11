-- tables: array/hash, insert/remove/sort/concat, length, next/pairs/ipairs
local t = {3, 1, 4, 1, 5, 9, 2, 6}
table.sort(t)
print(table.concat(t, ","))
table.sort(t, function(a,b) return a > b end)
print(table.concat(t, ","))
table.insert(t, 100); table.insert(t, 1, 0); table.remove(t, 2)
print(table.concat(t, ","), #t)
local h = {name="lua", version=5.4, [1]="one", [2]="two"}
local keys = {}
for k in pairs(h) do keys[#keys+1] = tostring(k) end
table.sort(keys)
print(table.concat(keys, ","))
local sum = 0
for i, v in ipairs({10,20,30,40}) do sum = sum + i*v end
print(sum)
print(table.unpack({1,2,3}))
print(select('#', 1, 2, 3), select(2, 'a', 'b', 'c'))
print(next({}), next({x=1}))
