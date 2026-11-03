# Home Assistant Gmail notification examples

These optional automations use Home Assistant's existing Google Mail integration.
No Google credentials belong in the Trend Playlist app or repository.

## Before enabling

1. Install and test the official Google Mail integration.
2. In Developer Tools → States, identify the entity named **Trend Playlist preview**
   (usually `sensor.trend_playlist_preview`). Substitute its actual entity ID below.
3. In Developer Tools → Actions, identify your Gmail notify action. Replace
   `notify.YOUR_GMAIL_NOTIFY_ACTION` with that exact action.
4. Replace `YOUR_EMAIL_ADDRESS` with the destination email address.
5. Add these automations via the YAML automation editor, or adapt them in
   `automations.yaml`. Do not paste secrets into the YAML.

## Weekly preview completed

Triggers on a new preview run timestamp, not on the sensor's generic state.
The email is sent only for a successful run with a ready proposal.

```yaml
alias: Trend Playlist - preview ready email
mode: single
triggers:
  - trigger: state
    entity_id: sensor.trend_playlist_preview
    attribute: last_run
conditions:
  - condition: template
    value_template: >
      {{ state_attr('sensor.trend_playlist_preview', 'ok') == true
         and state_attr('sensor.trend_playlist_preview', 'review') is mapping
         and state_attr('sensor.trend_playlist_preview', 'review').get('ready') == true }}
actions:
  - action: notify.YOUR_GMAIL_NOTIFY_ACTION
    data:
      title: "Trend Playlist: review ready"
      message: >
        The Down with the Kids proposal is ready to review in Home Assistant.
        Nothing has been published automatically.
      target:
        - YOUR_EMAIL_ADDRESS
```

## Preview failure

```yaml
alias: Trend Playlist - preview failed email
mode: single
triggers:
  - trigger: state
    entity_id: sensor.trend_playlist_preview
    attribute: last_run
conditions:
  - condition: template
    value_template: >
      {{ state_attr('sensor.trend_playlist_preview', 'ok') == false }}
actions:
  - action: notify.YOUR_GMAIL_NOTIFY_ACTION
    data:
      title: "Trend Playlist: preview failed"
      message: >
        The latest playlist preview failed. Check the Trend Playlist app logs
        before retrying. No automatic publish was attempted.
      target:
        - YOUR_EMAIL_ADDRESS
```

## Publish verified

```yaml
alias: Trend Playlist - publish verified email
mode: single
triggers:
  - trigger: state
    entity_id: sensor.trend_playlist_preview
    attribute: published_at
conditions:
  - condition: template
    value_template: >
      {{ state_attr('sensor.trend_playlist_preview', 'publish_status') == 'verified'
         and state_attr('sensor.trend_playlist_preview', 'published_at') not in [none, ''] }}
actions:
  - action: notify.YOUR_GMAIL_NOTIFY_ACTION
    data:
      title: "Trend Playlist: TIDAL publish verified"
      message: >
        The approved Down with the Kids playlist update has completed and
        passed track verification. Check TIDAL for the final playlist.
      target:
        - YOUR_EMAIL_ADDRESS
```

## Publish failure — important limitation

The current worker does not persist a distinct timestamp for failed publish
attempts. An automation watching `publish_status` can miss a short-lived
`running` state between 30-second polls, particularly after an earlier
failure. **Do not rely on an email as the sole failure alarm.** Inspect the
app status and recovery journal after publishing. A durable publish-result
event/timestamp is planned before enabling reliable failure alerts.

## Safety

These examples send notifications only. They do not call approval, preflight
or publish actions, and they do not modify TIDAL.
