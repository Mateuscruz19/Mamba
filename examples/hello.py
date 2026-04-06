x = 10
y = 3.14
print(x)
print(y)


def fact(n):
    if n <= 1:
        return 1
    return n * fact(n - 1)


print(fact(5))

i = 0
while i < 3:
    print(i)
    i = i + 1

if x == 10 and not False:
    print("ok")
