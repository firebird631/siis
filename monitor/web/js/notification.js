function notify(notification) {
    let when = notification['timestamp'] || 'now';
    let message = notification['message'] || "";
    let title = notification['title'] || "SiiS";

    let notif = $('<div class="toast" role="alert" aria-live="polite" aria-atomic="true" data-delay="2000">' +
        '<div class="toast-header">' +
          '<strong class="mr-auto">' + title + '</strong>' +
          '<small>' + when + '</small>' +
          '<button type="button" class="ml-2 mb-1 close" data-dismiss="toast" aria-label="Close">' +
            '<span aria-hidden="true" style="color: black;">&times;</span>' +
          '</button>' + 
        '</div>' +
        '<div class="toast-body">' + message + '</div>' +
      '</div>');

    $('#notifications').append(notif);
    notif.toast('show');

    notif.on('hidden.bs.toast', function () {
        notif.remove();
    });
}
