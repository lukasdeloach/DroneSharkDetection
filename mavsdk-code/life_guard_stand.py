# Author - Lukas DeLoach
class LifeGuardStand:
    def __init__(self, name, latitude, longitude):
        self.name = name
        self.latitude = latitude
        self.longitude = longitude
        self.notify = False
    
    def notifySwimmers(self):
        if self.notify == True:
            print("A shark has been spotted! Please leave the water.")


