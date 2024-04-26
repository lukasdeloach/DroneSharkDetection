$(document).ready(function() {
    var currentStand = 0;

    function fetchNotifications() {
        $.ajax({
            url: 'notification.txt',
            type: 'GET',
            success: function(data) {
                var lines = data.split('\n');
                var notifications = {};
                lines.forEach(function(line) {
                    var parts = line.split(', ');
                    var name = parts[0];
                    var lat = parts[1];
                    var lng = parts[2];
                    var distance = parts[3];
                    notifications[name] = {lat: lat, lng: lng, distance: distance};
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
            existingNotifications.each(function() {
                if ($(this).text().includes(name)) {
                    isNew = false;
                    return false;
                }
            });
            if (isNew) {
                var notificationText = 'Shark detected near ' + name + ', Lat: ' + newNotifications[name].lat + ', Lng: ' +
                     newNotifications[name].lng + ', distance from stand: ' + Math.ceil(newNotifications[name].distance.split(' ')[0]*1000) 
                    + ' m, time: ' + new Date();
                $('#notifications').append('<div class="notification">' + notificationText + '</div>');
                $('#stand-' + currentStand).removeClass('alert');
                $('#stand-' + name.split(' ')[1]).addClass('alert');
                currentStand = name.split(' ')[1]
            }
        }
    }

    setInterval(fetchNotifications, 500);
});
