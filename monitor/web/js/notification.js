function notify(notification) {
    let when = notification['timestamp'] || 'now';
    let message = notification['message'] || "";
    let title = notification['title'] || "SiiS";
    let type = notification['type'] || "info";
    let color = '#fff';
    let body_bg_color = '#444';
    let now = new Date();
    let datetime = when != 'now' ? timestamp_to_date_str(when) + ' ' + timestamp_to_time_str(when) : timestamp_to_date_str(now) + ' ' + timestamp_to_time_str(now);
    let badge_type = 'info';

    let bg_color = '#375a7f';
    if (type == 'alert' || type == 'error') {
        bg_color = '#d62c1a';
        badge_type = 'danger';
    } else if (type == 'success' || type == 'ok') {
        bg_color = '#00bc8c';
        badge_type = 'success';
    } else if (type == 'info' || type == 'message') {
        bg_color = '#217dbb';
        badge_type = 'info';
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

    let table = $('div.console-list-entries').find('tbody');
    let row_entry = $('<tr class="console-message"></tr>');
    row_entry.append($('<td class="message-datetime">' + datetime + '</td>'));
    row_entry.append($('<td class="message-type"><span class="badge badge-' + badge_type + '">' + type + '</span></td>'));
    row_entry.append($('<td class="message-content">' + message + '</td>'));

    table.prepend(row_entry);

    if (table.children().length > 200) {
        table.children().filter(':gt(200)').remove();
    }
}

function audio_notify(mode) {
    // no audio in backtesting
    if (!window.audio.enabled || window.strategy.backtesting) {
        return;
    }

    let alt = window.audio.alt;

    if (mode == 'alert' && !alt) {
        document.getElementById("audio_alert").play();
    } else if (mode == 'alert' && alt) {
        document.getElementById("audio_alert2").play();
    } else if (mode == 'loose' && !alt) {
        document.getElementById("audio_loose").play();
    } else if (mode == 'loose' && alt) {
        document.getElementById("audio_loose2").play();
    } else if (mode == 'win' && !alt) {
        document.getElementById("audio_win").play();
    } else if (mode == 'win' && alt) {
        document.getElementById("audio_win2").play();
    } else if (mode == 'timeout') {
        document.getElementById("audio_timeout").play();
    } else if (mode == 'signal') {
        document.getElementById("audio_signal").play();
    } else if (mode == 'entry') {
        document.getElementById("audio_entry").play();
    }
}
