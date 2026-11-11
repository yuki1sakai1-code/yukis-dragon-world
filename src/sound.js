// Procedural Web Audio Synthesizer for Draconic Sanctum (Stone Grinding, Sword Clash, Shatter & Choir)

export class SoundEffects {
  constructor() {
    this.ctx = null;
    this.enabled = true; // Sound Effects (SE)
    this.bgmEnabled = true; // Background Music (BGM)
    this.bgmAudio = null;
    this.bgmStarted = false;
    this.bgmVolume = 0.45; // Balanced volume for epic orchestral atmosphere
  }

  init() {
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) {
        this.ctx = new AudioCtx();
      }
    }
    if (this.ctx && this.ctx.state === 'suspended') {
      this.ctx.resume().catch(() => { });
    }
  }

  initBGM(sourceUrl) {
    if (this.bgmAudio) return;

    const embeddedAudio = window.__EMBEDDED_ASSETS__?.audio;
    let src =
      embeddedAudio?.['Beyond_the_Great_Crest.mp3'] ||
      embeddedAudio?.['./assets/audio/Beyond_the_Great_Crest.mp3'] ||
      embeddedAudio?.['/assets/audio/Beyond_the_Great_Crest.mp3'] ||
      sourceUrl ||
      './assets/audio/Beyond_the_Great_Crest.mp3';

    try {
      this.bgmAudio = new Audio();
      this.bgmAudio.src = src;
      this.bgmAudio.loop = true;
      this.bgmAudio.volume = this.bgmVolume;
      this.bgmAudio.preload = 'none';
    } catch (e) {
      console.warn('Failed to initialize BGM audio element:', e);
    }
  }

  playBGM() {
    if (!this.bgmEnabled) return;
    if (!this.bgmAudio) {
      this.initBGM();
    }
    if (this.bgmAudio) {
      this.bgmAudio.volume = this.bgmVolume;
      const promise = this.bgmAudio.play();
      if (promise !== undefined) {
        promise
          .then(() => {
            this.bgmStarted = true;
          })
          .catch((err) => {
            // Wait for user gesture due to browser autoplay policies
            console.log('BGM playback waiting for user gesture:', err?.message || err);
          });
      }
    }
  }

  pauseBGM() {
    if (this.bgmAudio) {
      this.bgmAudio.pause();
    }
  }

  toggleBGM() {
    this.bgmEnabled = !this.bgmEnabled;
    if (this.bgmEnabled) {
      this.playBGM();
    } else {
      this.pauseBGM();
    }
    return this.bgmEnabled;
  }

  setBGMVolume(volume) {
    this.bgmVolume = Math.max(0, Math.min(1, volume));
    if (this.bgmAudio) {
      this.bgmAudio.volume = this.bgmVolume;
    }
  }

  toggle() {
    this.enabled = !this.enabled;
    return this.enabled;
  }

  playSelect() {
    if (!this.enabled) return;
    this.init();
    if (!this.ctx) return;

    const now = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(520, now);
    osc.frequency.exponentialRampToValueAtTime(780, now + 0.14);

    gain.gain.setValueAtTime(0.08, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.16);

    osc.connect(gain);
    gain.connect(this.ctx.destination);
    osc.start(now);
    osc.stop(now + 0.17);
  }

  playStoneSlide(duration = 0.65) {
    if (!this.enabled) return;
    this.init();
    if (!this.ctx) return;

    const now = this.ctx.currentTime;
    // Filtered noise + low rumble for heavy stone statue grinding across marble
    const bufferSize = Math.floor(this.ctx.sampleRate * duration);
    const buffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < bufferSize; i++) {
      data[i] = (Math.random() * 2 - 1) * 0.6;
    }

    const noise = this.ctx.createBufferSource();
    noise.buffer = buffer;

    const filter = this.ctx.createBiquadFilter();
    filter.type = 'bandpass';
    filter.frequency.setValueAtTime(140, now);
    filter.frequency.linearRampToValueAtTime(210, now + duration * 0.5);
    filter.frequency.linearRampToValueAtTime(110, now + duration);
    filter.Q.value = 2.2;

    const gain = this.ctx.createGain();
    gain.gain.setValueAtTime(0.01, now);
    gain.gain.linearRampToValueAtTime(0.16, now + 0.08);
    gain.gain.setValueAtTime(0.14, now + duration - 0.1);
    gain.gain.exponentialRampToValueAtTime(0.001, now + duration);

    noise.connect(filter);
    filter.connect(gain);
    gain.connect(this.ctx.destination);
    noise.start(now);
    noise.stop(now + duration);

    // Heavy stone thud at end of slide
    this.playThud(now + duration - 0.05, 0.18);
  }

  playThud(startTime, volume = 0.22) {
    if (!this.enabled || !this.ctx) return;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();
    osc.type = 'triangle';
    osc.frequency.setValueAtTime(95, startTime);
    osc.frequency.exponentialRampToValueAtTime(32, startTime + 0.18);

    gain.gain.setValueAtTime(volume, startTime);
    gain.gain.exponentialRampToValueAtTime(0.001, startTime + 0.2);

    osc.connect(gain);
    gain.connect(this.ctx.destination);
    osc.start(startTime);
    osc.stop(startTime + 0.21);
  }

  playSwordStrikeAndShatter() {
    if (!this.enabled) return;
    this.init();
    if (!this.ctx) return;

    const now = this.ctx.currentTime;

    // 1. Metallic weapon clang harmonics
    const freqs = [880, 1340, 2120, 3190];
    freqs.forEach((f, idx) => {
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = idx % 2 === 0 ? 'sawtooth' : 'square';
      osc.frequency.setValueAtTime(f, now);
      osc.frequency.exponentialRampToValueAtTime(f * 0.85, now + 0.35);

      gain.gain.setValueAtTime(0.07 / (idx + 1), now);
      gain.gain.exponentialRampToValueAtTime(0.0008, now + 0.35);

      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start(now);
      osc.stop(now + 0.36);
    });

    // 2. Massive bass impact boom
    this.playThud(now, 0.42);

    // 3. Crumbling stone & marble shards cascade
    const shardCount = 9;
    for (let i = 0; i < shardCount; i++) {
      const delay = 0.04 + i * 0.055 + Math.random() * 0.03;
      this.playShardBounce(now + delay, 0.14 * Math.pow(0.82, i));
    }
  }

  playShardBounce(startTime, volume) {
    if (!this.ctx) return;
    const dur = 0.09;
    const bufferSize = Math.floor(this.ctx.sampleRate * dur);
    const buffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < bufferSize; i++) {
      data[i] = (Math.random() * 2 - 1) * Math.exp(-i / (bufferSize * 0.35));
    }
    const src = this.ctx.createBufferSource();
    src.buffer = buffer;

    const filter = this.ctx.createBiquadFilter();
    filter.type = 'bandpass';
    filter.frequency.value = 600 + Math.random() * 1400;
    filter.Q.value = 3.0;

    const gain = this.ctx.createGain();
    gain.gain.setValueAtTime(volume, startTime);
    gain.gain.exponentialRampToValueAtTime(0.001, startTime + dur);

    src.connect(filter);
    filter.connect(gain);
    gain.connect(this.ctx.destination);
    src.start(startTime);
    src.stop(startTime + dur);
  }

  playCheckHorn() {
    if (!this.enabled) return;
    this.init();
    if (!this.ctx) return;

    const now = this.ctx.currentTime;
    [220, 277.18, 329.63].forEach((freq) => {
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(freq, now);

      const filter = this.ctx.createBiquadFilter();
      filter.type = 'lowpass';
      filter.frequency.setValueAtTime(900, now);

      gain.gain.setValueAtTime(0.001, now);
      gain.gain.linearRampToValueAtTime(0.06, now + 0.08);
      gain.gain.exponentialRampToValueAtTime(0.0008, now + 0.75);

      osc.connect(filter);
      filter.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start(now);
      osc.stop(now + 0.78);
    });
  }
}

