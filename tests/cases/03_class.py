class Animal:
    def __init__(self, name):
        self.name = name
    def speak(self):
        return self.name + " makes a sound"

class Dog(Animal):
    def speak(self):
        return self.name + " says woof"

a = Animal("cat")
d = Dog("rex")
print(a.speak())
print(d.speak())
