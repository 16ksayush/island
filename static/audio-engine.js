/* =========================================================================
   Archive 19 — Audio crossfade engine (T10)

   Responsibilities (docs/ARCHITECTURE.md §6):
   - Landing: loop the theme GLOBAL ambient: /static/audio/global/{theme}_ambient.mp3
   - Level page: CROSSFADE the global ambient OUT while the level track fades IN.
       * existing level -> /static/audio/{theme}/level_{id}.mp3
       * missing level  -> the proxied fallback_audio URL from /api/levels/{id}/photos
   - Volume ramp ~1.5s; no two tracks ever play at full volume at once.
   - Auto-play defensive: browsers block audio until a user gesture. We attempt
     play() and, if it rejects, arm a one-shot listener that resumes on the first
     pointer/key/touch interaction. Everything fails silently if still blocked.

   SECURITY: this module only ever touches /static/... and /api/... URLs handed
   to it. It NEVER constructs a Google Drive URL and never sees the API key.
   ========================================================================= */
(function () {
  "use strict";

  var FADE_MS = 1500; // ~1.5s ramp to match the visual theme transition
  var STEP_MS = 40;
  var TARGET_VOL = 0.6; // comfortable loop volume

  // Each "channel" wraps an <audio> element + an active fade timer.
  function makeChannel() {
    var el = new Audio();
    el.loop = true;
    el.preload = "auto";
    el.volume = 0;
    el.crossOrigin = "anonymous";
    return { el: el, timer: null, wantPlaying: false };
  }

  function clearFade(ch) {
    if (ch.timer) {
      clearInterval(ch.timer);
      ch.timer = null;
    }
  }

  // Defensive play(): returns a promise that never rejects loudly.
  function tryPlay(ch, engine) {
    var p = ch.el.play();
    if (p && typeof p.then === "function") {
      p.catch(function () {
        // Auto-play blocked — arm a one-shot gesture resume.
        engine._armGesture();
      });
    }
  }

  function fade(ch, to, engine, onDone) {
    clearFade(ch);
    var from = ch.el.volume;
    var steps = Math.max(1, Math.round(FADE_MS / STEP_MS));
    var delta = (to - from) / steps;
    var i = 0;

    if (to > 0) {
      ch.wantPlaying = true;
      tryPlay(ch, engine);
    }

    ch.timer = setInterval(function () {
      i += 1;
      var v = from + delta * i;
      if (i >= steps) {
        v = to;
        clearFade(ch);
        if (to <= 0) {
          ch.wantPlaying = false;
          try {
            ch.el.pause();
          } catch (e) {
            /* ignore */
          }
        }
        if (onDone) onDone();
      }
      ch.el.volume = Math.min(1, Math.max(0, v));
    }, STEP_MS);
  }

  function AudioEngine() {
    this.ambient = makeChannel(); // global theme ambient
    this.level = makeChannel(); // per-level track
    this._gestureArmed = false;
    this._boundGesture = this._onGesture.bind(this);
  }

  // Arm a one-shot resume of any channel that wants to be playing, fired on the
  // first real user gesture. Idempotent.
  AudioEngine.prototype._armGesture = function () {
    if (this._gestureArmed) return;
    this._gestureArmed = true;
    var opts = { once: true, passive: true };
    document.addEventListener("pointerdown", this._boundGesture, opts);
    document.addEventListener("keydown", this._boundGesture, opts);
    document.addEventListener("touchstart", this._boundGesture, opts);
  };

  AudioEngine.prototype._onGesture = function () {
    this._gestureArmed = false;
    var self = this;
    [this.ambient, this.level].forEach(function (ch) {
      if (ch.wantPlaying && ch.el.paused) {
        tryPlay(ch, self);
      }
    });
  };

  // Landing: play the global ambient for the given theme.
  AudioEngine.prototype.playAmbient = function (theme) {
    var src = "/static/audio/global/" + theme + "_ambient.mp3";
    if (this.ambient.el.getAttribute("src") !== src) {
      this.ambient.el.src = src;
    }
    fade(this.ambient, TARGET_VOL, this);
  };

  // Level page: crossfade ambient OUT, level track IN.
  // `src` is either /static/audio/{theme}/level_{id}.mp3 or a proxied
  // /api/levels/{id}/media/{file_id} fallback URL.
  AudioEngine.prototype.crossfadeToLevel = function (src) {
    if (this.level.el.getAttribute("src") !== src) {
      this.level.el.src = src;
    }
    fade(this.ambient, 0, this); // wind global ambient down
    fade(this.level, TARGET_VOL, this); // scale the level track up
  };

  // Swap the ambient source mid-flight (used when the theme toggles on the
  // landing page without a full reload — kept here for completeness).
  AudioEngine.prototype.swapAmbient = function (theme) {
    var self = this;
    fade(this.ambient, 0, this, function () {
      self.playAmbient(theme);
    });
  };

  // Stop everything (e.g. page teardown).
  AudioEngine.prototype.stopAll = function () {
    fade(this.ambient, 0, this);
    fade(this.level, 0, this);
  };

  // Expose a singleton on window so inline page scripts can drive it.
  window.Archive19Audio = new AudioEngine();
})();
