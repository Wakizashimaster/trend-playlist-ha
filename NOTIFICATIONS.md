# Home Assistant notifications

Trend Playlist uses Home Assistant's existing notification actions, not Gmail credentials
inside the app. You can use Google Mail or substitute any compatible notify action.

## Setup

1. Test the official Google Mail integration in **Developer Tools → Actions**.
2. Find the entity ID for **Trend Playlist preview** in **Developer Tools → States**.
   The default is `sensor.trend_playlist_preview`.
3. Replace `notify.YOUR_GMAIL_ACTION` with your actual notification action, and
   `YOUR_EMAIL` with your recipient address.
4. Update both the Home Assistant app and HACS integration to **0.2.2** before
   enabling the automations below.

The app exposes durable completion attributes on the preview sensor:

| Attribute | Meaning |
| --- | --- |
| `preview_result_at` | New timestamp after **every** completed preview, successful or failed |
| `preview_result` | `success` or `failed` |
| `publish_result_at` | New timestamp after **every** completed publishing attempt |
| `publish_status` | `verified` or `failed` after completion |
| `published_at` | Timestamp of the last verified publish; null after a failed attempt |

A changed timestamp is a better trigger than a state that may remain `ready`
or `failed` across successive runs. Do not use **Run actions** to test triggers;
it bypasses automation conditions.

## Preview ready

```yaml
alias: Trend Playlist - preview ready
mode: single
triggers:
  - trigger: state
    entity_id: sensor.trend_playlist_preview
    attribute: preview_result_at
conditions:
  - condition: template
    value_template: >
      {{ trigger.from_state is not none
         and trigger.to_state is not none
         and trigger.to_state.attributes.get('preview_result') == 'success'
         and trigger.to_state.attributes.get('review', {}).get('ready') == true }}
actions:
  - action: notify.YOUR_GMAIL_ACTION
    data:
      title: "Trendee: playlist preview ready"
      message: >
        A new Down with the Kids proposal is ready to review in Home Assistant.
        No TIDAL changes have been published.
      target:
        - YOUR_EMAIL
```

## Preview failed

```yaml
alias: Trend Playlist - preview failed
mode: single
triggers:
  - trigger: state
    entity_id: sensor.trend_playlist_preview
    attribute: preview_result_at
conditions:
  - condition: template
    value_template: >
      {{ trigger.from_state is not none
         and trigger.to_state is not none
         and trigger.to_state.attributes.get('preview_result') == 'failed' }}
actions:
  - action: notify.YOUR_GMAIL_ACTION
    data:
      title: "Trendee: preview failed"
      message: >
        The playlist preview failed. Check the Trend Playlist app logs.
        Nothing was published automatically.
      target:
        - YOUR_EMAIL
```

## Publish verified

```yaml
alias: Trend Playlist - publish verified
mode: single
triggers:
  - trigger: state
    entity_id: sensor.trend_playlist_preview
    attribute: publish_result_at
conditions:
  - condition: template
    value_template: >
      {{ trigger.from_state is not none
         and trigger.to_state is not none
         and trigger.to_state.attributes.get('publish_status') == 'verified' }}
actions:
  - action: notify.YOUR_GMAIL_ACTION
    data:
      title: "Trendee: TIDAL publish verified"
      message: >
        The approved Down with the Kids playlist update completed and
        passed track verification.
      target:
        - YOUR_EMAIL
```

## Publish failed — inspect before retrying

```yaml
alias: Trend Playlist - publish failed
mode: single
triggers:
  - trigger: state
    entity_id: sensor.trend_playlist_preview
    attribute: publish_result_at
conditions:
  - condition: template
    value_template: >
      {{ trigger.from_state is not none
         and trigger.to_state is not none
         and trigger.to_state.attributes.get('publish_status') == 'failed' }}
actions:
  - action: notify.YOUR_GMAIL_ACTION
    data:
      title: "Trendee: publishing failed — action required"
      message: >
        A TIDAL publishing attempt failed. Do not retry publishing blindly.
        Inspect the app logs and recovery journal and verify the live playlist
        before taking any further action.
      target:
        - YOUR_EMAIL
```

## Reliability and safety

The result timestamps are persisted in the app configuration and survive app
restarts. Home Assistant polls every 30 seconds. A notification can still be
missed if Home Assistant is offline when a run completes or if an automation
is disabled. These examples are not a guaranteed-delivery queue.

Automations only send notifications. They never approve, preflight, or publish
a playlist. The Google Mail integration is optional.
