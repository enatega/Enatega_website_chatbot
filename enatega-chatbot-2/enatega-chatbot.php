<?php
/**
 * Plugin Name: Enatega Chatbot
 * Description: Renders a chat page that talks to the Railway RAG API + stores chats as a Custom Post Type.
 * Version:     1.1.3
 * Author:      Ninjas Code
 */

if (!defined('ABSPATH')) exit;

/** ====== API endpoints ====== */
define('ENATEGA_CHAT_BASE',     'https://enategawebsitechatbot-production.up.railway.app');
define('ENATEGA_CHAT_ENDPOINT', ENATEGA_CHAT_BASE . '/chat');
define('ENATEGA_CHAT_STREAM',   ENATEGA_CHAT_BASE . '/chat_stream');

/** ====== Security token for saving chats (set in wp-config.php ideally) ====== */
if (!defined('ENATEGA_LOG_TOKEN')) {
  define('ENATEGA_LOG_TOKEN', 'change-me-please');
}


// -----send user info to backend
function enatega_build_user_token() {
  if (!is_user_logged_in()) return '';

  if (!defined('ENATEGA_USER_SIGNING_SECRET') || !ENATEGA_USER_SIGNING_SECRET) return '';

  $u = wp_get_current_user();

  // Choose what you want Python to know:
  $payload = [
    'iss'   => home_url(),
    'iat'   => time(),
    'exp'   => time() + 3600, // 1 hour
    'uid'   => (int) $u->ID,
    'uname' => (string) $u->user_login,

    // OPTION A: send email (PII)
    'email' => (string) $u->user_email,

    // OPTION B: instead of email, comment the line above and use:
    // 'email_hash' => hash('sha256', strtolower(trim($u->user_email))),
  ];

  $json = wp_json_encode($payload, JSON_UNESCAPED_SLASHES);
  $b64  = rtrim(strtr(base64_encode($json), '+/', '-_'), '=');
  $sig  = hash_hmac('sha256', $b64, ENATEGA_USER_SIGNING_SECRET);

  return $b64 . '.' . $sig;
}

/** ====== Register CPT: enatega_chat ====== */
add_action('init', function () {
  register_post_type('enatega_chat', [
    'label'           => 'Enatega Chats',
    'labels'          => [
      'name'          => 'Enatega Chats',
      'singular_name' => 'Enatega Chat',
      'add_new'       => 'Add New',
      'add_new_item'  => 'Add New Chat',
      'edit_item'     => 'Edit Chat',
      'new_item'      => 'New Chat',
      'view_item'     => 'View Chat',
      'search_items'  => 'Search Chats',
    ],
    'public'          => false,
    'show_ui'         => true,
    'show_in_menu'    => true,
    'menu_position'   => 80,
    'menu_icon'       => 'dashicons-format-chat',
    'supports'        => ['title', 'editor'],
    'show_in_rest'    => true,
    'capability_type' => 'post',
  ]);
});

/** ====== REST route to upsert a chat transcript into CPT ====== */
add_action('rest_api_init', function () {
  register_rest_route('enatega/v1', '/save_chat', [
    'methods'  => 'POST',
    'callback' => function (WP_REST_Request $req) {
      $token = $req->get_param('token');
      if (!$token || $token !== ENATEGA_LOG_TOKEN) {
        return new WP_REST_Response(['error' => 'forbidden'], 403);
      }

      $p = $req->get_json_params();
      $session_id = sanitize_text_field($p['session_id'] ?? '');
      $visitor_id = sanitize_text_field($p['visitor_id'] ?? '');
      $started_at = intval($p['started_at'] ?? (time() * 1000));
      $last_active= intval($p['last_active'] ?? (time() * 1000));
      $page_urls  = is_array($p['page_urls'] ?? null) ? array_map('esc_url_raw', $p['page_urls']) : [];
      $messages   = $p['messages'] ?? [];

      if (!$session_id || !is_array($messages)) {
        return new WP_REST_Response(['error' => 'bad_request'], 400);
      }

      // Sanitize messages
      $safe_msgs = [];
      foreach ($messages as $m) {
        $role = ($m['role'] === 'assistant') ? 'assistant' : 'user';
        $html = wp_kses_post($m['html'] ?? '');
        $ts   = intval($m['ts'] ?? (time() * 1000));
        $safe_msgs[] = ['role' => $role, 'html' => $html, 'ts' => $ts];
      }

      // Build JSON for storage
      $content_json = wp_json_encode([
        'session_id' => $session_id,
        'visitor_id' => $visitor_id,
        'started_at' => $started_at,
        'last_active'=> $last_active,
        'page_urls'  => $page_urls,
        'messages'   => $safe_msgs,
      ], JSON_UNESCAPED_SLASHES);

      // Build human-readable transcript for post_content
      $transcript = '';
      foreach ($safe_msgs as $m) {
        $role = ucfirst($m['role']);
        $line = trim(strip_tags($m['html']));
        $transcript .= "$role: $line\n\n";
      }

      // Find existing post by session_id
      $existing = get_posts([
        'post_type'      => 'enatega_chat',
        'posts_per_page' => 1,
        'fields'         => 'ids',
        'meta_query'     => [
          ['key' => '_enatega_session_id', 'value' => $session_id, 'compare' => '=']
        ],
      ]);

      $title = 'Chat ' . substr($session_id, 0, 8) . ' • ' . gmdate('Y-m-d H:i', $started_at/1000) . 'Z';

      $postarr = [
        'post_type'      => 'enatega_chat',
        'post_status'    => 'publish',
        'post_title'     => $title,
        'post_content'   => $transcript, // readable transcript
        'post_date_gmt'  => gmdate('Y-m-d H:i:s', $last_active/1000),
        'post_modified_gmt' => gmdate('Y-m-d H:i:s', $last_active/1000),
      ];

 if ($existing) {
    $postarr['ID'] = $existing[0];
    $post_id = wp_update_post($postarr, true);
} else {
    $post_id = wp_insert_post($postarr, true);
    if (!is_wp_error($post_id)) {
        add_post_meta($post_id, '_enatega_session_id', $session_id, true);
    }
}

if (is_wp_error($post_id)) {
    return new WP_REST_Response(['error' => 'save_failed', 'detail' => $post_id->get_error_message()], 500);
}

// ✅ Always update meta AFTER confirming post_id
if ($post_id) {
    update_post_meta($post_id, '_enatega_json', $content_json);
    update_post_meta($post_id, '_enatega_visitor_id', $visitor_id);
    update_post_meta($post_id, '_enatega_started_at', $started_at);
    update_post_meta($post_id, '_enatega_last_active', $last_active);
    update_post_meta($post_id, '_enatega_page_urls', $page_urls);
}


      return ['ok' => true, 'post_id' => $post_id];
    },
    'permission_callback' => '__return_true',
  ]);
});

/** ====== Daily cleanup: delete chats older than 7 days ====== */
register_activation_hook(__FILE__, function () {
  if (!wp_next_scheduled('enatega_cpt_cleanup')) {
    wp_schedule_event(time(), 'daily', 'enatega_cpt_cleanup');
  }
});
add_action('enatega_cpt_cleanup', function () {
  $q = new WP_Query([
    'post_type'      => 'enatega_chat',
    'post_status'    => 'publish',
    'posts_per_page' => -1,
    'date_query'     => [
      [
        'column' => 'post_modified_gmt',
        'before' => '7 days ago',
        'inclusive' => true
      ]
    ],
    'fields'         => 'ids',
  ]);
  if ($q->have_posts()) {
    foreach ($q->posts as $pid) {
      wp_delete_post($pid, true);
    }
  }
});

/** ====== Assets ====== */
add_action('wp_enqueue_scripts', function () {
  $base = plugin_dir_url(__FILE__) . 'assets/';
  wp_enqueue_style('enatega-chat-css', $base . 'chat.css', [], time());
  wp_enqueue_script('enatega-chat-js',  $base . 'chat.js', [], time(), true);

  wp_localize_script('enatega-chat-js', 'ENATEGA_CHAT_CFG', [
    'endpoint'       => ENATEGA_CHAT_ENDPOINT,
    'streamEndpoint' => ENATEGA_CHAT_STREAM,
    'useStream'      => true,
    'saveEndpoint'   => rest_url('enatega/v1/save_chat'),
    'logToken'       => ENATEGA_LOG_TOKEN,
     'userToken'      => enatega_build_user_token(),
  ]);
});

/** ====== Shortcode ====== */
function enatega_chat_shortcode($atts) {
  ob_start(); ?>
  <div class="enatega-chat-widget">
    <button class="enatega-chat-toggle" id="enatega-chat-toggle">
        <div class="enatega-chat-toggle-bot-img">
			<img src="https://onboarding.enatega.com/wp-content/uploads/2026/02/chatbot-icon.webp" alt="Chat Icon">
		</div>
    </button>
    <div class="enatega-chat" id="enatega-chat-box" style="display:none;">
      <div class="enatega-chat__header">
        <div class="enatega-chat__title">Enatega Assistant</div>
        <div class="enatega-chat__subtitle">Ask me anything about Enatega</div>
        <button class="enatega-chat__close" id="enatega-chat-close">✕</button>
      </div>
      <div class="enatega-chat__msgs" id="enatega-chat-msgs" aria-live="polite"></div>
      <form class="enatega-chat__form" id="enatega-chat-form">
        <input id="enatega-chat-input" type="text" autocomplete="off" placeholder="Type your message…" />
        <button id="enatega-chat-send" type="submit">Send</button>
      </form>
      <div class="enatega-chat__footnote" id="enatega-chat-footnote"></div>
    </div>
  </div>
  <?php
  return ob_get_clean();
}
add_shortcode('enatega_chat', 'enatega_chat_shortcode');




/* =======================================================================
 * ADMIN UX ENHANCEMENTS
 * ======================================================================= */
add_action('init', function () {
  remove_post_type_support('enatega_chat', 'editor');
});

add_action('add_meta_boxes', function () {
  add_meta_box(
    'enatega_chat_transcript',
    'Transcript (Raw JSON)',
    'enatega_render_chat_transcript_box',
    'enatega_chat',
    'normal',
    'high'
  );
});

function enatega_render_chat_transcript_box($post) {
  $raw = get_post_meta($post->ID, '_enatega_json', true);

  // fallback to post_content if json not stored in meta
  if (!$raw) {
    $raw = get_post_field('post_content', $post->ID);
  }

  $data = json_decode($raw, true);

  // If still no JSON, just print raw text
  if (!$data || !is_array($data)) {
    echo '<div style="padding:10px;background:#fff;border:1px solid #ddd;border-radius:6px;">';
    echo nl2br(esc_html($raw ?: 'No transcript available.'));
    echo '</div>';
    return;
  }

  // Pretty print chat messages
  echo '<div style="border:1px solid #ddd;border-radius:6px;padding:10px;background:#fff;max-height:600px;overflow:auto;">';
  foreach ($data['messages'] as $m) {
    $role = ucfirst($m['role']);
    $msg  = wp_kses_post($m['html']);
    echo '<p><strong>' . esc_html($role) . ':</strong> ' . $msg . '</p>';
  }
  echo '</div>';
}




/** Add friendly columns in the list table */
add_filter('manage_enatega_chat_posts_columns', function ($cols) {
  $new = [];
  foreach ($cols as $k=>$v) {
    $new[$k] = $v;
    if ($k === 'title') {
      $new['en_last']    = 'Last Active';
      $new['en_count']   = 'Messages';
      $new['en_visitor'] = 'Visitor';
    }
  }
  return $new;
});

add_action('manage_enatega_chat_posts_custom_column', function ($col, $post_id) {
  if ($col === 'en_last') {
    $ts = get_post_meta($post_id, '_enatega_last_active', true);
    echo $ts ? esc_html(gmdate('Y-m-d H:i', intval($ts)/1000)) . 'Z' : '—';
  } elseif ($col === 'en_count') {
    $raw = get_post_meta($post_id, '_enatega_json', true);
    $data = $raw ? json_decode($raw, true) : null;
    echo is_array($data['messages'] ?? null) ? intval(count($data['messages'])) : 0;
  } elseif ($col === 'en_visitor') {
    $vid = get_post_meta($post_id, '_enatega_visitor_id', true);
    echo $vid ? esc_html(substr($vid,0,10)) . '…' : '—';
  }
}, 10, 2);
