function notify(notification) {
    let when = notification['timestamp'] || 'now';
    let message = notification['message'] || "";
    let title = notification['title'] || "SiiS";
    let type = notification['type'] || "info";
    let color = '#fff';
    let body_bg_color = '#444';

    let bg_color = '#375a7f';
    if (type == 'alert' || type == 'error') {
        bg_color = '#d62c1a';
    } else if (type == 'success' || type == 'ok') {
        bg_color = '#00bc8c';
    } else if (type == 'info' || type == 'message') {
        bg_color = '#217dbb';
    }

    let notif = $('<div class="toast" role="alert" aria-live="polite" aria-atomic="true" data-delay="2000">' +
        '<div class="toast-header" style="background-color: ' + bg_color + '">' +
          '<strong class="mr-auto" style="color: ' + color + '">' + title + '</strong>' +
          '<small style="color: ' + color + '"">' + when + '</small>' +
          '<button type="button" class="ml-2 mb-1 close" data-dismiss="toast" aria-label="Close">' +
            '<span aria-hidden="true" style="color: ' + color + '">&times;</span>' +
          '</button>' + 
        '</div>' +
        '<div class="toast-body" style="background-color: ' + body_bg_color + '">' + message + '</div>' +
      '</div>');

    $('#notifications').append(notif);
    notif.toast('show');

    notif.on('hidden.bs.toast', function () {
        notif.remove();
    });
}
