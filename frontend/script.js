$(document).ready(function() {
    var currentStand = 0;
    var currentWarningLevel = "";

    function fetchNotifications() {
        $.ajax({
            url: 'notification.txt',
            type: 'GET',
            success: function(data) {
                var lines = data.split('\n');
                var notifications = {};
                lines.forEach(function(line) {
                    console.log(line)
                    var parts = line.split(', ');
                    var name = parts[0];
                    var lat = parts[1];
                    var lng = parts[2];
                    var distance = parts[3];
                    var warning = parts[4]
                    notifications[name] = {lat: lat, lng: lng, distance: distance, warning: warning};
                });
                updateNotifications(notifications);
            },
            error: function(xhr, status, error) {
                console.error('Error fetching notifications:', error);
            }
        });
    }

    function updateNotifications(newNotifications) {
        var existingNotifications = $('#notifications').children();
        for (var name in newNotifications) {
            var isNew = true;
            var newAlert = true;
            existingNotifications.each(function() {
                if ($(this).text().includes(name)) {
                    console.log($(this).text())
                    if(newNotifications[name].warning === currentWarningLevel){
                        newAlert = false
                    }
                    isNew = false;    
                }
            });
            if (isNew || newAlert) {
                var warningLevel = newNotifications[name].warning;
                console.log(newNotifications[name])
                console.log(warningLevel)
                var notificationText = warningLevel + 'Shark detected near ' + name + ', Lat: ' + newNotifications[name].lat + ', Lng: ' +
                    newNotifications[name].lng + ', distance from stand: ' + Math.ceil(newNotifications[name].distance.split(' ')[0]*1000) +
                    ' m, time: ' + new Date();
                var $notification = $('<div class="notification">' + notificationText + '</div>');
                
                // Check if the warning level is "DANGER" and set the background color accordingly
                if (warningLevel === "DANGER: ") {
                    $notification.css('background-color', 'red');
                }

                else if (warningLevel === "WARNING: ") {
                    $notification.css('background-color', 'yellow');
                }
    
                $('#notifications').append($notification);
                $('#stand-' + currentStand).removeClass('alert');
                $('#stand-' + name.split(' ')[1]).addClass('alert');
                currentStand = name.split(' ')[1]
                currentWarningLevel = warningLevel
            }
        }
    }
    
    setInterval(fetchNotifications, 500);
});
