
  (function () {
    'use strict';

    // ════════════════════════════════════════════════════════
    // Ask Lure — Tab Voice Copy Variant Pools
    // ════════════════════════════════════════════════════════
    
    // ── Generate Tab — Scenario selection quips (under ~15 words) ──
    const generateCeoQuips = [
      "Authority is a powerful drug. When the boss emails, people stop thinking.",
      "Impersonating the CEO is a classic. Everyone wants to please the boss.",
      "A quick word from the top can make anyone bypass security protocols."
    ];
    
    const generateItQuips = [
      "System alert! People click fast when they think their tech is broken.",
      "Nothing spreads panic like a fake IT password reset request.",
      "Fake update alerts are the perfect bait to drop malicious code."
    ];
    
    const generateHrQuips = [
      "Curiosity about policy updates or pay reviews gets them every time.",
      "HR emails sound official and boring—the perfect cover for a trap.",
      "An update on benefits is hard to ignore. Click first, ask later!"
    ];
    
    const generateInvoiceQuips = [
      "Money talks, especially when a supplier demands urgent payment.",
      "Fake invoices create panic in accounting. Panicked people make mistakes.",
      "An unpaid bill is a classic way to bypass rational suspicion."
    ];

    // ── Generate Tab — Success line variants ──
    const generateSuccessLines = [
      "Lure formulated successfully. Review the indicators below!",
      "Hook set! Check out the psychological triggers in this lure.",
      "The perfect bait is ready. Inspect the red flags in the card below.",
      "Lure crafted. See if you can spot all the threat indicators!",
      "Bait is in the water. Examine the cues that make this email work."
    ];

    // ── Generate Tab — Error line variants ──
    const generateErrorLines = [
      "Formulation failed. Lure offline.",
      "Engine failure. The AI couldn't craft this lure.",
      "Lure offline. Something jammed in the AI generator."
    ];

    // ── Spot Phish Tab — Correct guess variants ──
    const spotCorrectPool = [
      "Spot on! You saw right through that. Typically, they use {tactic} to bypass your logic.",
      "Sharp eyes! That was indeed the fake. Notice how it relied on {tactic}?",
      "Correct! You didn't fall for the {tactic} angle. Keep that guard up!",
      "Perfect! You caught the threat indicator. {tactic} is a classic social engineering trick.",
      "Got it! A real attacker would use {tactic} just like that to sneak past."
    ];

    // ── Spot Phish Tab — Incorrect guess variants ──
    const spotIncorrectPool = [
      "Not quite! That was a legitimate email. Look closer at the urgency indicators next time.",
      "Ah, that one slipped by! The other mail was the phish. Don't worry, defense is a practice.",
      "Incorrect. The real threat used a sneakier layout. Look out for unexpected requests next round!",
      "Missed it! Phishing can look incredibly ordinary. Compare the sender domains next time.",
      "Wrong choice, but a good lesson. The fake email relied on subtle cues. Keep training!"
    ];

    // ── Risk Score Tab — High risk score variants ──
    const riskHighPool = [
      "Ouch! That's a target-rich environment. Attackers are salivating at those odds.",
      "Danger zone! With numbers like that, one bad click could lock down the whole ship.",
      "Yikes! You're swimming in shark-infested waters with no cage. Time to train!",
      "Critical exposure. Your team needs interactive training before a real attacker tests them."
    ];

    // ── Risk Score Tab — Medium risk score variants ──
    const riskMedPool = [
      "Moderate waters. You have some nets cast, but a few clever fish could still slip through.",
      "Decent start, but complacency is a slow killer. Keep sharpening those defenses.",
      "Not terrible, but not secure either. A determined attacker would find a way in.",
      "Halfway there. Regular simulation training would turn those soft spots into armor."
    ];

    // ── Risk Score Tab — Low risk score variants ──
    const riskLowPool = [
      "Impressive! You've built a strong harbor. Even the sneakiest lures will struggle here.",
      "Smooth sailing! High hygiene makes phishing a tough sell. Don't let your guard down.",
      "Excellent defense posture. You've trained well, but remember, the sea never stops churning.",
      "Looking sharp! Low exposure is hard-earned. Keep running simulations to stay alert."
    ];

    // ── Index Tracking to prevent repeats ──
    const lastShownIndices = {
      ceo_fraud: -1,
      it_alert: -1,
      hr_update: -1,
      invoice: -1,
      generate_success: -1,
      generate_error: -1,
      spot_correct: -1,
      spot_incorrect: -1,
      risk_high: -1,
      risk_med: -1,
      risk_low: -1
    };

    /* ================================================================
       Visitor Profile & Persistence Layer (100% Client-side)
       
       Schema ('lure_visitor_profile' in localStorage):
       {
         visitCount: number,             // Increment once per browser session
         hasCompletedTour: boolean,      // True if a tour was completed
         lastScenarioUsed: string|null,  // Last generated scenario (e.g. 'ceo_fraud')
         lastVisitTimestamp: number      // Epoch timestamp of last session
       }
       ================================================================ */
    const PROFILE_KEY = 'lure_visitor_profile';
    
    let visitorProfile = {
      visitCount: 0,
      hasCompletedTour: false,
      completedTours: {},
      lastScenarioUsed: null,
      lastVisitTimestamp: Date.now()
    };

    function loadVisitorProfile() {
      try {
        const stored = localStorage.getItem(PROFILE_KEY);
        if (stored) {
          visitorProfile = JSON.parse(stored);
          if (!visitorProfile.completedTours) {
            visitorProfile.completedTours = {};
          }
        }
      } catch (e) {
        console.error("Failed to parse visitor profile:", e);
      }
    }

    function saveVisitorProfile() {
      try {
        localStorage.setItem(PROFILE_KEY, JSON.stringify(visitorProfile));
      } catch (e) {
        console.error("Failed to save visitor profile:", e);
      }
    }

    function initVisitorProfile() {
      loadVisitorProfile();
      
      const isNewSession = !sessionStorage.getItem('lure_session_counted');
      if (isNewSession) {
        visitorProfile.visitCount = (visitorProfile.visitCount || 0) + 1;
        visitorProfile.lastVisitTimestamp = Date.now();
        sessionStorage.setItem('lure_session_counted', 'true');
        saveVisitorProfile();
      }
    }

    initVisitorProfile();

    // ── Mascot Images & Preloading ──
    const mascotImages = {
      idle: "/static/images/lure/lure_idle.png",
      active: "/static/images/lure/lure_thinking.png",
      success: "/static/images/lure/lure_success.png",
      error: "/static/images/lure/lure_error.png",
      blink: "/static/images/lure/lure_blink.png"
    };

    const preloadedImages = {};
    for (const key in mascotImages) {
      preloadedImages[key] = new Image();
      preloadedImages[key].src = mascotImages[key];
    }

    // Shared small Lure message avatar generator
    window.getLureAvatarHtml = function(state = 'idle') {
      const src = mascotImages[state] || mascotImages['idle'];
      return `<img src="${src}" alt="Lure AI" class="pb-msg-avatar" data-state="${state}" style="width: 28px; height: 28px; object-fit: contain; flex-shrink: 0; filter: drop-shadow(0 0 4px var(--primary-glow));">`;
    };

    // Helper to temporarily update dialogue avatars to success/error/active state
    window.updateMessageAvatar = function(containerId, state, duration = 0) {
      const container = document.getElementById(containerId);
      if (!container) return;
      container.innerHTML = getLureAvatarHtml(state);
      if (duration > 0) {
        setTimeout(() => {
          container.innerHTML = getLureAvatarHtml('idle');
        }, duration);
      }
    };
    
    // Initialize all static dialogue avatars
    function initDialogueAvatars() {
      const genCont = document.getElementById('pb-gen-avatar-container');
      if (genCont) genCont.innerHTML = getLureAvatarHtml('idle');
      
      const spotCont = document.getElementById('pb-spotphish-avatar-container');
      if (spotCont) spotCont.innerHTML = getLureAvatarHtml('idle');
      
      const riskCont = document.getElementById('pb-riskscore-avatar-container');
      if (riskCont) riskCont.innerHTML = getLureAvatarHtml('idle');
      
      const spotIlCont = document.getElementById('pb-spotphish-il-avatar-container');
      if (spotIlCont) spotIlCont.innerHTML = getLureAvatarHtml('idle');
    }
    if (document.readyState === 'complete') {
      initDialogueAvatars();
    } else {
      window.addEventListener('load', initDialogueAvatars);
    }

    // ── Mascot State & Crossfade Controller ──
    let currentImageElement = document.getElementById('pb-avatar-img-a');
    let hiddenImageElement = document.getElementById('pb-avatar-img-b');
    let currentMascotState = 'idle';
    let isBlinking = false;
    let blinkTimeout = null;
    let animationPlayingUntil = 0; // Timestamp safety to prevent blinking mid-animation

    function setMascotImage(state) {
      const url = mascotImages[state];
      if (!url || !currentImageElement || !hiddenImageElement) return;

      // Avoid unnecessary crossfade if target image is already set
      if (currentImageElement.src === new URL(url, window.location.href).href) {
        return;
      }

      hiddenImageElement.src = url;

      const performCrossfade = () => {
        hiddenImageElement.classList.add('visible');
        currentImageElement.classList.remove('visible');

        const temp = currentImageElement;
        currentImageElement = hiddenImageElement;
        hiddenImageElement = temp;
      };

      if (hiddenImageElement.complete) {
        performCrossfade();
      } else {
        hiddenImageElement.onload = performCrossfade;
      }
    }

    function changeMascotState(state) {
      currentMascotState = state;

      // Success or error states trigger one-shot animations
      if (state === 'success' || state === 'error') {
        if (blinkTimeout) {
          clearTimeout(blinkTimeout);
          blinkTimeout = null;
        }
        isBlinking = false;
        animationPlayingUntil = Date.now() + 500; // Pause blink for 500ms
      }

      // If mid-blink, let the blink cycle end before updating visible state
      if (!isBlinking) {
        setMascotImage(state);
      }
    }

    // ── Randomized Mascot Blinking ──
    function scheduleNextBlink() {
      if (blinkTimeout) clearTimeout(blinkTimeout);
      if (panelOpen) return; // Pause blinking while in header

      const randomDelay = Math.random() * 4000 + 3000; // 3 to 7 seconds
      blinkTimeout = setTimeout(() => {
        // Skip blink if success/error animation is active
        if (Date.now() < animationPlayingUntil) {
          scheduleNextBlink();
          return;
        }

        isBlinking = true;
        setMascotImage('blink');

        blinkTimeout = setTimeout(() => {
          isBlinking = false;
          setMascotImage(currentMascotState);
          scheduleNextBlink();
        }, 150); // Blink duration 150ms
      }, randomDelay);
    }

    // Start blink loop once page is loaded
    if (document.readyState === 'complete') {
      scheduleNextBlink();
    } else {
      window.addEventListener('load', scheduleNextBlink);
    }

    // ── Sync Mascot Image with Class changes on #pb-host ──
    const syncHost = document.getElementById('pb-host');
    if (syncHost) {
      const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
          if (mutation.attributeName === 'class') {
            const className = syncHost.className;
            let state = 'idle';
            if (className.includes('pb-active')) state = 'active';
            else if (className.includes('pb-success')) state = 'success';
            else if (className.includes('pb-error')) state = 'error';
            changeMascotState(state);
          }
        });
      });
      observer.observe(syncHost, { attributes: true });
    }

    // ── Cursor-Follow Mascot Tilt (replaces pupil movement) ──
    (function() {
      const avatar = document.getElementById('pb-avatar');
      const wrap = document.getElementById('pb-avatar-wrap');
      if (!avatar || !wrap) return;

      let animationFrameId = null;

      function onMouseMove(e) {
        if (animationFrameId) return;

        animationFrameId = requestAnimationFrame(() => {
          animationFrameId = null;

          const rect = avatar.getBoundingClientRect();
          const avatarCenterX = rect.left + rect.width / 2;
          const avatarCenterY = rect.top + rect.height / 2;

          const distX = e.clientX - avatarCenterX;
          const distY = e.clientY - avatarCenterY;
          const distance = Math.hypot(distX, distY);

          if (distance < 150 && distance > 0) {
            const maxTilt = 4.0; // max 4 degrees rotation
            const proximityFactor = (150 - distance) / 150;
            const angle = (distX / distance) * maxTilt * proximityFactor;
            wrap.style.transform = `rotate(${angle.toFixed(2)}deg)`;
          } else {
            wrap.style.transform = 'rotate(0deg)';
          }
        });
      }

      function onMouseLeave() {
        if (animationFrameId) {
          cancelAnimationFrame(animationFrameId);
          animationFrameId = null;
        }
        wrap.style.transform = 'rotate(0deg)';
      }

      window.addEventListener('mousemove', onMouseMove, { passive: true });
      document.addEventListener('mouseleave', onMouseLeave);
    })();

    function getRandomVariant(pool, poolKey) {
      if (!pool || pool.length === 0) return '';
      if (pool.length === 1) return pool[0];
      
      let index;
      const lastIndex = lastShownIndices[poolKey];
      do {
        index = Math.floor(Math.random() * pool.length);
      } while (index === lastIndex);
      
      lastShownIndices[poolKey] = index;
      return pool[index];
    }

    // Helper: Staged narration for loading states
    function startLoadingNarration(el, stages, delay = 800, maxDuration = 6000, longWaitMsg = "Still working, taking a bit longer...") {
      if (!el || !stages || stages.length === 0) return () => {};
      let currentStage = 0;
      el.textContent = stages[currentStage];
      
      const intervalId = setInterval(() => {
        currentStage++;
        if (currentStage < stages.length) {
          el.textContent = stages[currentStage];
        } else {
          clearInterval(intervalId);
        }
      }, delay);

      const timeoutId = setTimeout(() => {
        clearInterval(intervalId);
        el.textContent = longWaitMsg;
      }, maxDuration);

      return () => {
        clearInterval(intervalId);
        clearTimeout(timeoutId);
      };
    }

    // Helper: Esc html content
    function esc(s) {
      if (!s) return '';
      return s.toString()
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }

    const host      = document.getElementById('pb-host');
    const avatar    = document.getElementById('pb-avatar');
    if (host && host.parentNode !== document.body) {
      document.body.appendChild(host);
    }
    const panel     = document.getElementById('pb-panel');
    const teaser    = document.getElementById('pb-teaser');
    const fvPopover = document.getElementById('pb-first-visit-popover');
    const inlineSec = document.getElementById('pb-inline-section');

    let panelOpen = false;
    let fvOpen    = false;
    let expanded  = false;
    let resizeHandler = null;
    let scrollHandler = null;

    // Cache pre-warmed generator scenario
    const _cache = {};
    let _busy = false;

    /* ── Positioning & Layout Clamping ── */
    function repositionPanel() {
      if (!panelOpen) return;
      const avatarR = avatar.getBoundingClientRect();
      const panelW  = panel.offsetWidth;
      const panelH  = panel.offsetHeight;

      // Position panel relative to avatar
      let left = avatarR.left + (avatarR.width / 2) - (panelW / 2);
      let top  = avatarR.top - panelH - 12; // 12px gap above avatar

      // Clamp coordinates to viewport boundaries
      const margin = 10;
      left = Math.max(margin, Math.min(left, window.innerWidth - panelW - margin));
      
      // If panel overflows the top edge of screen, open it downwards
      if (top < margin) {
        top = avatarR.bottom + 12;
      }
      // Clamp bottom
      top = Math.max(margin, Math.min(top, window.innerHeight - panelH - margin));

      panel.style.left = left + 'px';
      panel.style.top  = top + 'px';
      
      if (avatar.classList.contains('pb-in-header')) {
        updateHeaderAvatarPosition(false);
      }
    }

    /* ── Animate Avatar into/out of Panel Header ── */
    function updateHeaderAvatarPosition(animateSwim = false) {
      if (!panelOpen) return;
      const placeholder = document.getElementById('pb-header-avatar-placeholder');
      if (!placeholder) return;
      
      const rectStart = host.getBoundingClientRect();
      const rectTarget = placeholder.getBoundingClientRect();
      
      const dx = rectTarget.left - rectStart.left;
      const dy = rectTarget.top - rectStart.top;
      const scale = placeholder.offsetWidth / avatar.offsetWidth;
      
      if (animateSwim) {
        avatar.classList.add('pb-transitioning');
        avatarWrap.classList.add('pb-swim-active');
        setTimeout(() => {
          avatarWrap.classList.remove('pb-swim-active');
          avatar.classList.remove('pb-transitioning');
          avatar.classList.add('pb-in-header');
        }, 450);
      } else {
        avatar.style.transition = 'none';
        avatar.style.transform = `translate(${dx}px, ${dy}px) scale(${scale})`;
        void avatar.offsetWidth; // force reflow
        avatar.style.transition = '';
        return;
      }
      
      avatar.style.transform = `translate(${dx}px, ${dy}px) scale(${scale})`;
    }

    function repositionFvPopover() {
      if (!fvOpen) return;
      const avatarR = avatar.getBoundingClientRect();
      const popW    = fvPopover.offsetWidth;
      const popH    = fvPopover.offsetHeight;

      let left = avatarR.left + (avatarR.width / 2) - (popW / 2);
      let top  = avatarR.top - popH - 12;

      const margin = 10;
      left = Math.max(margin, Math.min(left, window.innerWidth - popW - margin));
      if (top < margin) {
        top = avatarR.bottom + 12;
      }
      top = Math.max(margin, Math.min(top, window.innerHeight - popH - margin));

      fvPopover.style.left = left + 'px';
      fvPopover.style.top  = top + 'px';
    }

    function updateAvatarBadge() {
      const badge = document.getElementById('pb-avatar-badge');
      if (!badge) return;

      if (unseenCalloutsCount === 0) {
        badge.style.display = 'none';
        badge.textContent = '';
        badge.className = '';
      } else {
        badge.style.display = 'flex';
        if (unseenCalloutsCount === 1) {
          badge.className = 'pb-dot';
          badge.textContent = '';
        } else {
          badge.className = 'pb-count';
          badge.textContent = unseenCalloutsCount;
        }
      }
    }

    function toggleMaximize() {
      const isMaximized = panel.classList.contains('pb-panel-maximized');
      const maxIcon = document.querySelector('#pb-max-btn i');
      const maxBtn = document.getElementById('pb-max-btn');

      // 1. Fade out content immediately
      panel.classList.add('pb-content-transitioning');

      // 2. Perform resize after the fade out completes (150ms)
      setTimeout(() => {
        if (!isMaximized) {
          // Capture normal bounds
          const currHeight = panel.offsetHeight;
          const currWidth = panel.offsetWidth;
          const currRect = panel.getBoundingClientRect();

          // Set inline styles so transition starts from here
          panel.style.width = currWidth + 'px';
          panel.style.height = currHeight + 'px';
          panel.style.left = currRect.left + 'px';
          panel.style.top = currRect.top + 'px';

          void panel.offsetHeight; // reflow

          // Maximize
          panel.classList.add('pb-panel-maximized');

          // Update button states
          if (maxIcon) {
            maxIcon.className = 'ti ti-minimize';
          }
          if (maxBtn) {
            maxBtn.setAttribute('title', 'Collapse panel');
            maxBtn.setAttribute('aria-label', 'Collapse');
          }
          
          setTimeout(() => {
            updateHeaderAvatarPosition(true);
          }, 0);
        } else {
          // Capture current maximized size
          const maxRect = panel.getBoundingClientRect();
          panel.style.width = maxRect.width + 'px';
          panel.style.height = maxRect.height + 'px';
          panel.style.left = maxRect.left + 'px';
          panel.style.top = maxRect.top + 'px';

          void panel.offsetHeight; // reflow

          // Collapse class
          panel.classList.remove('pb-panel-maximized');

          // Temporarily reset inline height/width to compute normal target size
          panel.style.width = '';
          panel.style.height = '';

          const avatarR = avatar.getBoundingClientRect();
          const normalW = 380;
          let normalLeft = avatarR.left + (avatarR.width / 2) - (normalW / 2);
          const margin = 10;
          normalLeft = Math.max(margin, Math.min(normalLeft, window.innerWidth - normalW - margin));

          const targetHeight = panel.offsetHeight;
          let normalTop = avatarR.top - targetHeight - 12;
          if (normalTop < margin) {
            normalTop = avatarR.bottom + 12;
          }
          normalTop = Math.max(margin, Math.min(normalTop, window.innerHeight - targetHeight - margin));

          // Reset to max size to start transition
          panel.style.width = maxRect.width + 'px';
          panel.style.height = maxRect.height + 'px';
          panel.style.left = maxRect.left + 'px';
          panel.style.top = maxRect.top + 'px';

          void panel.offsetHeight; // reflow

          // Animate back to normal size
          panel.style.width = normalW + 'px';
          panel.style.height = targetHeight + 'px';
          panel.style.left = normalLeft + 'px';
          panel.style.top = normalTop + 'px';
          
          setTimeout(() => {
            updateHeaderAvatarPosition(true);
          }, 0);

          // Clean up inline styles once transition completes
          setTimeout(() => {
            if (!panel.classList.contains('pb-panel-maximized') && panelOpen) {
              panel.style.width = '';
              panel.style.height = '';
              repositionPanel();
            }
          }, 350);

          // Update button states
          if (maxIcon) {
            maxIcon.className = 'ti ti-maximize';
          }
          if (maxBtn) {
            maxBtn.setAttribute('title', 'Expand to page');
            maxBtn.setAttribute('aria-label', 'Expand');
          }
        }

        // 3. Fade content back in after resize finishes (350ms)
        setTimeout(() => {
          panel.classList.remove('pb-content-transitioning');
          repositionPanel();
        }, 350);
      }, 150);
    }

    function openPanel() {
      if (fvOpen) closeFvPopover();
      
      if (panel._closeTimeout) {
        clearTimeout(panel._closeTimeout);
        panel._closeTimeout = null;
      }
      
      panelOpen = true;
      panel.setAttribute('aria-hidden', 'false');
      
      // Restore last active tab from sessionStorage if it exists
      const lastTab = sessionStorage.getItem('pb_active_tab');
      if (lastTab) {
        const targetBtn = panel.querySelector(`.pb-tab-btn[data-tab="${lastTab}"]`);
        if (targetBtn) {
          panel.querySelectorAll('.pb-tab-btn, .pb-sidebar-tab-btn').forEach(b => {
            if (b.dataset.tab === lastTab) {
              b.classList.add('active');
            } else {
              b.classList.remove('active');
            }
          });
          panel.querySelectorAll('.pb-tab-panel').forEach(p => p.classList.remove('active'));
          const p = panel.querySelector(`#pb-tab-${lastTab}`);
          if (p) p.classList.add('active');
        }
      }
      
      panel.classList.add('pb-open');
      repositionPanel();
      avatar.setAttribute('aria-expanded', 'true');
      
      // Animate swim into header
      updateHeaderAvatarPosition(true);
      

      
      // Clear proactive badge on open
      unseenCalloutsCount = 0;
      updateAvatarBadge();
      
      // Mark first visit popover dismissed when panel is explicitly opened
      localStorage.setItem('first_visit_popover_dismissed', 'true');

      // Customize greeting dialogue if Lure is idle (not currently generating)
      const dialogue = document.getElementById('pb-dialogue-text');
      if (dialogue && !_busy) {
        loadVisitorProfile();
        if (visitorProfile.visitCount > 1) {
          if (!visitorProfile.hasCompletedTour) {
            dialogue.textContent = "Welcome back! Let's take the walkthrough, or pick a scenario below.";
          } else if (visitorProfile.lastScenarioUsed) {
            const scenarioNames = {
              'ceo_fraud': 'CEO Fraud',
              'it_alert': 'IT Support Alert',
              'hr_update': 'HR Policy Update',
              'invoice': 'Fake Invoice'
            };
            const friendly = scenarioNames[visitorProfile.lastScenarioUsed] || 'custom';
            dialogue.textContent = `Welcome back! We formulated a ${friendly} lure last time. Try a new one below!`;
          } else {
            dialogue.textContent = "Welcome back! Ready to formulate some high-conviction security lures?";
          }
        } else {
          dialogue.textContent = "Pick a scenario and I'll generate a real AI phishing lure \ud83e\uddea right now, live.";
        }
      }
    }

    function closePanel() {
      panelOpen = false;
      panel.classList.remove('pb-open');
      avatar.setAttribute('aria-expanded', 'false');
      
      // Animate swim back out to docked position
      avatar.classList.remove('pb-in-header');
      avatar.classList.add('pb-transitioning');
      avatarWrap.classList.add('pb-swim-active');
      avatar.style.transform = 'none';
      
      setTimeout(() => {
        avatar.classList.remove('pb-transitioning');
        avatarWrap.classList.remove('pb-swim-active');
        // Resume blinking
        scheduleNextBlink();
      }, 450);
      
      if (typeof resetIdleFidgetTimer === 'function') {
        resetIdleFidgetTimer();
      }
      
      // Wait for transition to finish before hiding from screen readers and resetting maximized state
      panel._closeTimeout = setTimeout(() => {
        panel._closeTimeout = null;
        panel.setAttribute('aria-hidden', 'true');
        
        // Reset maximized state on next open
        if (panel.classList.contains('pb-panel-maximized')) {
          panel.classList.remove('pb-panel-maximized');
          const maxIcon = document.querySelector('#pb-max-btn i');
          const maxBtn = document.getElementById('pb-max-btn');
          if (maxIcon) {
            maxIcon.className = 'ti ti-maximize';
          }
          if (maxBtn) {
            maxBtn.setAttribute('title', 'Expand to page');
            maxBtn.setAttribute('aria-label', 'Expand');
          }
          // Restore normal dimensions
          panel.style.width = '';
          panel.style.height = '';
          panel.style.top = '';
          panel.style.left = '';
        }
      }, 350);
    }

    function openFvPopover() {
      if (panelOpen) closePanel();
      fvOpen = true;
      fvPopover.classList.add('pb-open');
      repositionFvPopover();
    }

    function closeFvPopover() {
      fvOpen = false;
      fvPopover.classList.remove('pb-open');
    }

    const LURE_TEASERS = [
      "Want a tour? I'd love to show you around.",
      "New here? I can walk you through the platform.",
      "Click me anytime to generate a simulated phishing lure.",
      "Let's test your human defenses together!",
      "Need a guide? I'm ready when you are."
    ];

    // Teaser hover interaction
    avatar.addEventListener('pointerenter', () => {
      // Lazy pre-warm trigger
      prewarmCeoFraud();

      if (!panelOpen && !fvOpen) {
        const msgEl = document.getElementById('pb-teaser-msg');
        if (msgEl) {
          const rand = LURE_TEASERS[Math.floor(Math.random() * LURE_TEASERS.length)];
          msgEl.textContent = `"${rand}"`;
        }
        teaser.classList.add('pb-show');
      }
    });

    avatar.addEventListener('pointerleave', () => {
      teaser.classList.remove('pb-show');
    });

    /* ── Click / Close hooks ── */
    let preventClick = false;

    avatar.addEventListener('click', () => {
      if (preventClick) return;
      
      // Trigger squash-and-stretch animation
      avatar.classList.add('pb-squash-active');
      setTimeout(() => {
        avatar.classList.remove('pb-squash-active');
        
        loadVisitorProfile();
        const dismissed = localStorage.getItem('first_visit_popover_dismissed') === 'true';
        if (!dismissed && visitorProfile.visitCount === 1) {
          fvOpen ? closeFvPopover() : openFvPopover();
        } else {
          if (!dismissed) {
            localStorage.setItem('first_visit_popover_dismissed', 'true');
          }
          panelOpen ? closePanel() : openPanel();
        }
      }, 180);
    });

    document.getElementById('pb-close-btn').addEventListener('click', closePanel);

    const resetBtn = document.getElementById('pb-reset-visitor');
    if (resetBtn) {
      resetBtn.addEventListener('click', (e) => {
        e.preventDefault();
        localStorage.removeItem('lure_visitor_profile');
        localStorage.removeItem('first_visit_popover_dismissed');
        sessionStorage.removeItem('lure_session_counted');
        
        // Reset state
        visitorProfile = {
          visitCount: 1,
          hasCompletedTour: false,
          lastScenarioUsed: null,
          lastVisitTimestamp: Date.now()
        };
        
        const dialogue = document.getElementById('pb-dialogue-text');
        if (dialogue) {
          dialogue.textContent = "Pick a scenario and I'll generate a real AI phishing lure \ud83e\uddea right now, live.";
        }
        
        closePanel();
        openFvPopover();
      });
    }

    document.getElementById('pb-fv-walkthrough-btn').addEventListener('click', () => {
      localStorage.setItem('first_visit_popover_dismissed', 'true');
      closeFvPopover();
      openWalkthroughDirectly();
    });

    document.getElementById('pb-fv-generate-btn').addEventListener('click', () => {
      localStorage.setItem('first_visit_popover_dismissed', 'true');
      closeFvPopover();
      openPanel();
    });

    document.addEventListener('click', e => {
      if (panelOpen && !panel.contains(e.target) && !host.contains(e.target)) closePanel();
      if (fvOpen && !fvPopover.contains(e.target) && !host.contains(e.target)) closeFvPopover();
    });

    document.addEventListener('keydown', e => {
      if (e.key === 'Escape') {
        if (panelOpen) closePanel();
        if (fvOpen) closeFvPopover();
      }
    });

    /* ── Bounded drag — pointer events (not HTML5 drag API) ─────
       Bound zone: right 25% of viewport, full height
       Disabled on mobile (≤768px)                                */
    const DRAG_ZONE_FRAC = 0.25; // right 25%
    const DRAG_MARGIN    = 10;   // px from viewport edges
    let drag = null;

    function isMobile() { return window.innerWidth <= 768; }

    document.getElementById('pb-drag-handle').addEventListener('pointerdown', startDrag);
    avatar.addEventListener('pointerdown', startDrag);

    function startDrag(e) {
      if (isMobile()) return;
      if (e.target.closest('.pb-icon-btn') || e.target.closest('.pb-tab-btn')) return;
      
      const targetEl = e.currentTarget;
      targetEl.setPointerCapture && targetEl.setPointerCapture(e.pointerId);
      e.preventDefault();

      const hostR = host.getBoundingClientRect();
      drag = {
        pointerId: e.pointerId,
        target:    targetEl,
        startX:    e.clientX,
        startY:    e.clientY,
        origRight: window.innerWidth  - hostR.right,
        origBottom: window.innerHeight - hostR.bottom,
        hasMoved:  false
      };
    }

    document.addEventListener('pointermove', e => {
      if (!drag || isMobile()) return;
      const dx = drag.startX - e.clientX;
      const dy = drag.startY - e.clientY;

      if (!drag.hasMoved && (Math.abs(dx) > 4 || Math.abs(dy) > 4)) {
        drag.hasMoved = true;
      }

      if (!drag.hasMoved) return;

      // Compute new right/bottom for the HOST
      let newRight  = drag.origRight  + dx;
      let newBottom = drag.origBottom + dy;

      // Window-wide drag constraints (anywhere within the viewport with margin)
      newRight = Math.max(newRight, DRAG_MARGIN);
      newRight = Math.min(newRight, window.innerWidth - host.offsetWidth - DRAG_MARGIN);

      newBottom = Math.max(newBottom, DRAG_MARGIN);
      newBottom = Math.min(newBottom, window.innerHeight - host.offsetHeight - DRAG_MARGIN);

      host.style.right  = newRight  + 'px';
      host.style.bottom = newBottom + 'px';
      host.style.left   = 'auto';
      host.style.top    = 'auto';

      if (panelOpen) repositionPanel();
      if (fvOpen) repositionFvPopover();
    });

    document.addEventListener('pointerup', e => {
      if (!drag) return;
      if (drag.target) {
        drag.target.releasePointerCapture && drag.target.releasePointerCapture(drag.pointerId);
      }
      const wasDragged = drag.hasMoved;
      drag = null;
      if (wasDragged) {
        preventClick = true;
        setTimeout(() => { preventClick = false; }, 50);
      }
    });

    /* ── Tabs (Floating Panel) ─────────────────────────────────── */
    panel.querySelectorAll('.pb-tab-btn, .pb-sidebar-tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const tab = btn.dataset.tab;
        sessionStorage.setItem('pb_active_tab', tab);
        panel.querySelectorAll('.pb-tab-btn, .pb-sidebar-tab-btn').forEach(b => {
          if (b.dataset.tab === tab) {
            b.classList.add('active');
          } else {
            b.classList.remove('active');
          }
        });
        panel.querySelectorAll('.pb-tab-panel').forEach(p => p.classList.remove('active'));
        const p = panel.querySelector(`#pb-tab-${tab}`);
        if (p) p.classList.add('active');
        if (tab === 'tours') {
          renderToursList();
        }
        repositionPanel();
      });
    });

    /* ── Tabs (Maximized Fullscreen Takeover Modal) ────────────── */
    inlineSec.querySelectorAll('.pb-inline-tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const tab = btn.dataset.tab;
        inlineSec.querySelectorAll('.pb-inline-tab-btn').forEach(b => b.classList.remove('active'));
        inlineSec.querySelectorAll('.pb-inline-tab-panel').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        const p = inlineSec.querySelector(`#pb-tab-${tab}`);
        if (p) p.classList.add('active');
        if (tab === 'il-walkthrough') {
          renderToursList();
        }
      });
    });

    /* ── Maximize and Collapse handlers ── */
    document.getElementById('pb-max-btn').addEventListener('click', () => {
      // Toggle maximize in-place on the same panel
      if (!panelOpen) {
        // If closed, open directly as maximized
        panel.classList.add('pb-panel-maximized');
        const maxIcon = document.querySelector('#pb-max-btn i');
        const maxBtn = document.getElementById('pb-max-btn');
        if (maxIcon) {
          maxIcon.className = 'ti ti-minimize';
        }
        if (maxBtn) {
          maxBtn.setAttribute('title', 'Collapse panel');
          maxBtn.setAttribute('aria-label', 'Collapse');
        }
        openPanel();
      } else {
        toggleMaximize();
      }
    });

    document.getElementById('pb-inline-collapse').addEventListener('click', () => {
      exitWalkthrough();
      expanded = false;
      inlineSec.style.display = 'none';
    });

    function openWalkthroughDirectly() {
      openPanel();
      setTimeout(() => {
        const toursBtn = panel.querySelector('.pb-tab-btn[data-tab="tours"]');
        if (toursBtn) toursBtn.click();
      }, 50);
    }

    /* ── Generator API logic ── */
    const SCORE_AXES = {
      urgency: "Urgency",
      authority: "Authority Focus",
      believability: "Believability",
      obfuscation: "Obfuscation",
      personalization: "Personalisation"
    };

    function renderBait(container, baitScore) {
      container.innerHTML = '';
      if (!baitScore) return;
      Object.keys(SCORE_AXES).forEach(key => {
        const val = baitScore[key] || 0; // 0 - 100
        const labelText = SCORE_AXES[key];
        const row = document.createElement('div');
        row.className = 'pb-score-row';
        row.innerHTML = `
          <div class="pb-score-name">${esc(labelText)}</div>
          <div class="pb-score-track">
            <div class="pb-score-fill" style="width:0%; background:${val >= 75 ? 'var(--danger)' : val >= 45 ? 'var(--warning)' : 'var(--success,#34D399)'};"></div>
          </div>
          <div class="pb-score-num">${val}%</div>
        `;
        container.appendChild(row);
        setTimeout(() => {
          const fill = row.querySelector('.pb-score-fill');
          if (fill) fill.style.width = val + '%';
        }, 50);
      });
    }

    function annotate(html) {
      const escaped = esc(html);
      // Find Red-Flag definitions in markdown format [text](rf:tip)
      const rx = /\[([^\]]+)\]\(rf:([^)]+)\)/g;
      return escaped.replace(rx, (_, text, tip) => {
        return `<span class="pb-rf">${text}<span class="pb-rf-tip">${tip}</span></span>`;
      });
    }

    window.pbGen = function (scenario, isInline = false) {
      if (_busy) return;
      _busy = true;

      const prefix = isInline ? 'pb-il-' : 'pb-';
      const dialogue = document.getElementById('pb-dialogue-text');
      const loader = document.getElementById(prefix + 'gen-loader');
      const card = document.getElementById(prefix + 'card');
      const sender = document.getElementById(prefix + 'sender');
      const subject = document.getElementById(prefix + 'subject');
      const body = document.getElementById(prefix + 'body');
      const tacticText = document.getElementById(prefix + 'tactic');
      const meta = document.getElementById(prefix + 'meta');
      const errorMsg = document.getElementById(prefix + 'error');
      
      const baitSect = document.getElementById('pb-bait-section');
      const scoreBars = document.getElementById('pb-score-bars');

      // Reset
      if (errorMsg) errorMsg.style.display = 'none';
      card.style.display = 'none';
      if (meta) meta.style.display = 'none';
      if (baitSect) baitSect.style.display = 'none';
      loader.style.display = 'block';

      // Set avatar status
      host.className = 'pb-active';
      if (!isInline) {
        updateMessageAvatar('pb-gen-avatar-container', 'active');
      }

      let stopNarration = null;
      if (dialogue && !isInline) {
        dialogue.style.opacity = '0.5';
        let quip = '';
        if (scenario === 'ceo_fraud') quip = getRandomVariant(generateCeoQuips, 'ceo_fraud');
        else if (scenario === 'it_alert') quip = getRandomVariant(generateItQuips, 'it_alert');
        else if (scenario === 'hr_update') quip = getRandomVariant(generateHrQuips, 'hr_update');
        else if (scenario === 'invoice') quip = getRandomVariant(generateInvoiceQuips, 'invoice');
        else quip = 'Generating custom security lure...';
        
        const stages = [
          quip,
          "Analyzing target profile...",
          "Drafting message body...",
          "Calibrating authority angle...",
          "Polishing urgency triggers..."
        ];
        stopNarration = startLoadingNarration(dialogue, stages, 850, 6000, "Still crafting... a bit longer...");
      }

      function process(data) {
        if (stopNarration) stopNarration();
        loader.style.display = 'none';
        host.className = 'pb-success';
        if (!isInline) {
          updateMessageAvatar('pb-gen-avatar-container', 'success', 2500);
        }
        if (dialogue && !isInline) {
          dialogue.style.opacity = '1';
          dialogue.textContent = getRandomVariant(generateSuccessLines, 'generate_success');
        }
        _render(data, scenario, {
          sender: sender, subject: subject, body: body, card: card, meta: meta, tactic: tacticText,
          bait: baitSect, bars: scoreBars
        }, id => document.getElementById(id));
      }

      // Check pre-warmed cache
      if (_cache[scenario]) {
        setTimeout(() => {
          _busy = false;
          process(_cache[scenario]);
        }, 400);
        return;
      }

      const fd = new FormData();
      fd.append('scenario', scenario);

      fetch('/api/hero-demo-lure', { method: 'POST', body: fd })
        .then(r => {
          if (!r.ok) throw new Error('AI Lure Engine is currently busy. Try again later.');
          return r.json();
        })
        .then(j => {
          _busy = false;
          if (j && j.success) {
            // Save to cache
            _cache[scenario] = j;
            
            // Save last scenario to visitor profile
            loadVisitorProfile();
            visitorProfile.lastScenarioUsed = scenario;
            saveVisitorProfile();

            process(j);
          } else {
            throw new Error(j.message || 'Lure formulation failed.');
          }
        })
        .catch(err => {
          if (stopNarration) stopNarration();
          _busy = false;
          loader.style.display = 'none';
          host.className = 'pb-error';
          if (!isInline) {
            updateMessageAvatar('pb-gen-avatar-container', 'error', 2500);
          }
          if (dialogue && !isInline) {
            dialogue.style.opacity = '1';
            dialogue.textContent = getRandomVariant(generateErrorLines, 'generate_error');
          }
          errorMsg.style.display = 'block';
          errorMsg.textContent = err.message;
          if (isInline) repositionPanel();
        });
    };

    function _render(data, scenario, ids, $) {
      const getEl = id => {
        if (!id) return null;
        if (typeof id === 'string') return document.getElementById(id);
        return id;
      };
      
      const senderEl = getEl(ids.sender);
      const subjectEl = getEl(ids.subject);
      const tacticEl = getEl(ids.tactic);
      const cardEl = getEl(ids.card);
      const metaEl = getEl(ids.meta);
      const bodyEl = getEl(ids.body);
      const baitEl = getEl(ids.bait);
      const barsEl = getEl(ids.bars);
      
      if (senderEl) senderEl.textContent = data.sender_display || '';
      if (subjectEl) subjectEl.textContent = data.subject || '';
      if (tacticEl) tacticEl.innerHTML = 'Tactic: <strong>' + esc(data.phishing_tactic || '') + '</strong>';
      if (cardEl) cardEl.style.display = 'block';
      if (metaEl) metaEl.style.display = 'flex';
      repositionPanel();

      // Typewriter with red-flag annotation
      if (bodyEl) {
        bodyEl.innerHTML = '';
        const raw = data.body_text || '';
        let idx = 0;
        const spd = Math.max(5, Math.floor(1400 / Math.max(raw.length, 1)));
        function tick() {
          if (idx < raw.length) {
            idx++;
            bodyEl.innerHTML = annotate(raw.slice(0, idx));
            bodyEl.scrollTop = bodyEl.scrollHeight;
            setTimeout(tick, spd);
          } else {
            bodyEl.innerHTML = annotate(raw); // final pass
            if (baitEl && barsEl) {
              if (data.bait_score) {
                renderBait(barsEl, data.bait_score);
                baitEl.style.display = 'block';
              } else {
                baitEl.style.display = 'none';
              }
            }
            repositionPanel(); // Adjust position again after bait section shows/hides!
          }
        }
        tick();
      }
    }

    // Lazy pre-warm trigger on hover/tap
    let prewarmed = false;
    function prewarmCeoFraud() {
      if (prewarmed || _cache['ceo_fraud'] || _busy) return;
      prewarmed = true;
      const fd = new FormData(); fd.append('scenario', 'ceo_fraud');
      fetch('/api/hero-demo-lure', { method: 'POST', body: fd })
        .then(r => r.ok ? r.json() : null)
        .then(j => { if (j && j.success) _cache['ceo_fraud'] = j; })
        .catch(() => {});
    }


    /* ================================================================
       Interactive Walkthrough Engine (Global & Cross-Page support)
       ================================================================ */
    const WALKTHROUGH_CONFIGS = {
      core_workflow: [
        {
          targetId: "campaign-form",
          title: "The Full Simulation Loop",
          text: "You've already seen how to configure a campaign. This time, let's follow one all the way from launch, to target reaction, to AI-generated reports and sharing results. Confirm your details and let's go!",
          path: "/new-campaign"
        },
        {
          targetId: "campaigns-grid",
          title: "Tracking the Fleet",
          text: "Once campaigns launch, they appear right here on the dashboard. You can monitor overall open, click, and report rates at a glance. Let's look at the sent-emails inbox for our CEO Fraud Test.",
          path: "/dashboard"
        },
        {
          targetId: "wt-emails-inbox",
          title: "AI-Generated Inbox",
          text: "Here you inspect all generated simulation emails. Notice how each target gets a personalized message tailored to exploit human urgency. Let's see what happens if a target clicks the phishing link.",
          path: "/campaign-emails/0"
        },
        {
          targetId: "login-form",
          title: "The Phishing Click Outcome",
          text: "When a recipient clicks the phishing link, they land here. This realistic fake Microsoft login form harvests credentials for educational purposes, teaching the user in the moment while logging a Click event.",
          path: "/fake-login-demo"
        },
        {
          targetId: "thank-you-card-container",
          title: "The Active Reporting Outcome",
          text: "If instead the recipient reports the email using the PhishSim plug-in, they are redirected here. This reinforces the active defense habit, proving that employees can act as live sensors against real threats.",
          path: "/reporting-demo"
        },
        {
          targetId: "wt-report-hero",
          title: "AI Campaign Report",
          text: "This is the payoff. The AI constructs an agentic report measuring your Human Security Score™, key vulnerabilities, and custom department remediation steps to help you mitigate high-risk hotspots.",
          path: "/campaign-report/0"
        },
        {
          targetId: "pdf-dl-btn",
          title: "Exporting for Leadership",
          text: "Export your reports to PDF or CSV with a single click to share progress with your leadership team and compliance auditors. You've completed the complete PhishSim simulation loop!",
          path: "/campaign-report/0"
        }
      ],
      getting_started: [
        {
          targetId: "actual-terminal-wrapper",
          title: "Think Like the Threat",
          text: "I'm Lure, your AI security co-pilot. Ever wondered why phishing works so well? Attackers start by scouting public records and OSINT data—gathering the exact pieces they need to build trust before you even realize you're targeted.",
          path: "/"
        },
        {
          targetId: "threat-sandbox",
          title: "Inside the Hook",
          text: "Phishing succeeds because it's deeply personalized. In this Sandbox, you can safely generate lures and spot phishing emails to see how easily simple details can manipulate a person. Let's build a real campaign to see how this scales.",
          path: "/"
        },
        {
          targetId: "campaign_name",
          title: "Framing the Context",
          text: "To train a team effectively, the simulation has to feel real. Start by naming your campaign and choosing a target domain—this lets us customize the pretext so it mimics the actual, context-aware threats your staff faces daily.",
          path: "/new-campaign"
        },
        {
          targetId: "wt-scenarios-container",
          title: "Crafting the Angle",
          text: "What story will get them to click? Select a scenario like CEO Wire Fraud or a routine IT alert. I'll automatically spin up context-specific email copy tailored to hook the target's attention naturally.",
          path: "/new-campaign"
        },
        {
          targetId: "wt-delivery-grid",
          title: "Choosing the Path",
          text: "How do you want to test? You can run local sandboxed mock trials, dispatch live emails through SMTP, or choose Safe Send to route everything to Mailtrap so you can inspect your drafts with zero risk.",
          path: "/new-campaign"
        },
        {
          targetId: "consent_confirmed",
          title: "Cast the Line",
          text: "Ready to see who bites? Confirm your authorization and hit Create. I'll take care of the rest—dispatching the personalized lures and setting up the tracking to capture real engagement metrics.",
          path: "/new-campaign"
        },
        {
          targetId: "wt-dashboard-view",
          title: "Reading the Signals",
          text: "Here is where the data reveals itself. Your dashboard reports live open and click rates, showing you exactly how many targets fell for the pretext so you can measure your organization's true exposure.",
          path: "/dashboard"
        },
        {
          targetId: "mainTrendChart",
          title: "Charting Progress",
          text: "Notice the click-rate trend line? A high click rate isn't a failure—it's a diagnostic signal. The goal is to see this line slope downward over time as security habits strengthen and red flags become obvious.",
          path: "/dashboard"
        },
        {
          targetId: "wt-dashboard-view",
          title: "Where Next?",
          text: "Our onboarding tour is complete! Now you are ready to explore: why not launch your first simulated campaign, ask me a technical question in the Ask Lure tab, or test our standalone Header Analyzer?",
          path: "/dashboard"
        }
      ],
      campaign_launch: [
        { targetId: "actual-terminal-wrapper", title: "Terminal Queries", text: "First, let's look at my Sandbox Terminal. Here, you can type active security commands to query target email domains and analyze target vulnerabilities.", path: "/" },
        { targetId: "wt-create-campaign-btn", title: "Campaign Hub", text: "Ready to launch? We go to the Dashboard to create a campaign.", path: "/dashboard", redirectPath: "/new-campaign" },
        { targetId: "campaign-form", title: "Campaign Creator", text: "In this form, you configure targets and scenarios. Once launched, simulation results flow right back into the dashboard.", path: "/new-campaign" }
      ],
      lure_generation: [
        { targetId: "pb-avatar", title: "Formulating Lures", text: "This is my AI Lure Generator! I write personalized phishing emails on the fly based on threat scenarios you select.", path: "/" },
        { targetId: "campaign-form", title: "Injecting Targets", text: "To make these emails convincing, I can ingest CSV lists containing target names, departments, and titles to craft context-aware copy.", path: "/new-campaign" },
        { targetId: "pricing", title: "Scaling Simulation", text: "Once you are ready to deploy automated lures across your company, you can choose a subscription that scales to your target count.", path: "/" }
      ],
      attack_analysis: [
        { targetId: "attack-chain", title: "Attack Visualizations", text: "Take a look at this campaign attack chain. I'll help your security officers map how phishing templates, credential harvesters, and data breaches link together.", path: "/" },
        { targetId: "sec-hero", title: "Risk Profile Grading", text: "We will track every interaction and report detailed risk grades to help you prioritize training for vulnerable departments.", path: "/reports-demo" }
      ],
      tool_threat_analyzer: [
        { targetId: "tab-body", title: "Threat Analyzer Tab", text: "Welcome to the Threat Analyzer! First, choose whether you want to paste a raw email body to audit its text, or headers to trace its headers. I'll search the text for phishing indicators.", path: "/threat-analyzer" },
        { targetId: "ta-email-input", title: "Paste Raw Emails", text: "You can copy and paste any suspicious email copy here, or check out our preset forensic samples below to see what real-world CEO wire fraud or IT support alert pretexts look like.", path: "/threat-analyzer" },
        { targetId: "ta-analyze-btn", title: "Analyzing Indicators", text: "Click here to trigger my forensic analysis. I'll parse the copy, measure language urgency, search for suspicious domains, and highlight threat factors.", path: "/threat-analyzer" },
        { targetId: "ta-main-card", title: "Reading Results", text: "Once finished, I'll display the risk verdict badge, color-coded threat level score, and highlight exactly which phrases are dangerous right on the email card. Audit threat indicators with confidence!", path: "/threat-analyzer" }
      ],
      tool_header_analyzer: [
        { targetId: "headers-input", title: "Ingesting Raw Headers", text: "Welcome! Here, paste the raw internet headers of any email you wish to audit. Raw headers contain the technical route records, sender authentication keys, and delivery timestamps.", path: "/header-analyzer" },
        { targetId: "btn-preset-spf-fail", title: "Authentication Presets", text: "Need an example? Click one of my preset templates below, like this SPF authentication failure chip, to load real raw header content instantly.", path: "/header-analyzer" },
        { targetId: "trace-btn", title: "Trace Hop Path", text: "Click Trace Route to run my parser. I'll dissect the headers, extract hop-by-hop records, verify domain alignment, and evaluate anti-spoofing compliance.", path: "/header-analyzer" },
        { targetId: "ha-hop-stage", title: "Analyzing Hop Trails", text: "I'll display the hop sequence and trace security records like SPF, DKIM, and DMARC alignment status, plus highlight red flags to spot spoofed sender domains.", path: "/header-analyzer" }
      ],
      tool_url_decoder: [
        { targetId: "url-input", title: "Inspect Suspicious URLs", text: "Welcome! Copy any suspicious hyperlink you receive in an email and paste it here. Attackers love using shorteners and multi-hop redirects to mask dangerous sites.", path: "/url-decoder" },
        { targetId: "ud-input-body", title: "Redirect Presets", text: "Select one of my forensic samples below to see how I handle multi-hop redirect chains or links flagged by open threat feeds like URLhaus.", path: "/url-decoder" },
        { targetId: "trace-btn", title: "Run Trace Query", text: "Click Trace Link to trace the URL hops safely. I'll trigger a head query, follow redirect loops, expand shorteners, and inspect safety reputations.", path: "/url-decoder" },
        { targetId: "ud-chain-stage", title: "Visualizing Hops", text: "Once processed, I'll reveal every single redirect hop and display a simulated live browser preview so you can safely audit the final page without risk!", path: "/url-decoder" }
      ],
      tool_password_breach: [
        { targetId: "btn-tab-pw", title: "Password Strength Audit", text: "Welcome! First, evaluate any password's local strength using my real-time entropy tracker to verify it meets secure guidelines.", path: "/password-breach" },
        { targetId: "sec-audit-input-token", title: "Input Password", text: "Type a password here to test. I'll calculate characters, length, case variability, numeric complexity, and verify if it's too simple.", path: "/password-breach" },
        { targetId: "btn-tab-email", title: "Email Leak Scanner", text: "Next, click over to my Email tab. Here, paste any email address to audit public databases of known credential leaks.", path: "/password-breach" },
        { targetId: "pb-vault-card", title: "Audit Exposure Level", text: "Trigger the audit to inspect if the credentials have been compromised, letting you proactively update keys and maintain strong account security!", path: "/password-breach" }
      ]
    };

    let wtActive = false;
    let wtCurrentStep = 0;
    let wtSteps = [];
    let wtCurrentPage = 'full_tour';
    let isFirstStep = true;
    let gateListenersInitialized = false;

    function checkStepGate(stepIdx) {
      if (wtCurrentPage !== 'getting_started') return true; // Gate only the getting_started recommended tour
      
      if (stepIdx === 0) {
        // Step 1: Terminal query
        const terminalBody = document.getElementById('terminal-body');
        return !!(terminalBody && (terminalBody.textContent.includes('demo-corp.com') || terminalBody.textContent.includes('MX') || terminalBody.textContent.includes('SPF') || terminalBody.textContent.includes('DMARC') || terminalBody.children.length > 2));
      }
      if (stepIdx === 1) {
        // Step 2: Sandbox generate
        const emailCard = document.getElementById('pb-card');
        return !!(emailCard && emailCard.style.display !== 'none');
      }
      if (stepIdx === 2) {
        // Step 3: Campaign Name
        const nameInput = document.getElementById('campaign_name');
        return !!(nameInput && nameInput.value.trim().length >= 3);
      }
      if (stepIdx === 3) {
        // Step 4: Scenario Selection
        const scenarioChecked = document.querySelector('input[name="scenario"]:checked');
        return !!scenarioChecked;
      }
      if (stepIdx === 4) {
        // Step 5: Delivery Mode
        const deliveryChecked = document.querySelector('input[name="delivery_mode"]:checked');
        return !!deliveryChecked;
      }
      if (stepIdx === 5) {
        // Step 6: Consent checkbox
        const consentChecked = document.getElementById('consent_confirmed');
        return !!(consentChecked && consentChecked.checked);
      }
      return true; // Steps 7, 8, 9 are not gated
    }

    function initGateListeners() {
      if (gateListenersInitialized) return;
      gateListenersInitialized = true;

      // Watch terminal logs changes or general changes
      setInterval(() => {
        if (wtActive && wtCurrentPage === 'getting_started') {
          updateWalkthroughGate();
        }
      }, 400);

      // Event listener for inputs on campaign page
      document.body.addEventListener('input', (e) => {
        if (!wtActive || wtCurrentPage !== 'getting_started') return;
        if (e.target.id === 'campaign_name' || e.target.id === 'company_domain') {
          updateWalkthroughGate();
        }
      });

      document.body.addEventListener('change', (e) => {
        if (!wtActive || wtCurrentPage !== 'getting_started') return;
        if (e.target.name === 'scenario' || e.target.name === 'delivery_mode' || e.target.id === 'consent_confirmed') {
          updateWalkthroughGate();
        }
      });
    }

    function updateWalkthroughGate() {
      const satisfiesGate = checkStepGate(wtCurrentStep);
      const nextBtns = document.querySelectorAll('.pb-next-btn');
      const gatePrompts = document.querySelectorAll('.pb-gate-prompt');
      
      nextBtns.forEach(nextBtn => {
        if (satisfiesGate) {
          nextBtn.removeAttribute('disabled');
          nextBtn.classList.remove('pb-disabled');
          nextBtn.style.opacity = '1';
          nextBtn.style.cursor = 'pointer';
        } else {
          nextBtn.setAttribute('disabled', 'true');
          nextBtn.classList.add('pb-disabled');
          nextBtn.style.opacity = '0.4';
          nextBtn.style.cursor = 'not-allowed';
        }
      });

      gatePrompts.forEach(p => {
        p.style.display = satisfiesGate ? 'none' : 'flex';
      });
    }

    /* ── Walkthrough Helpers for Swimming and Particles ── */
    function createBubbleParticle(x, y) {
      const bubble = document.createElement('div');
      bubble.className = 'pb-bubble-particle';
      const size = Math.floor(Math.random() * 6) + 4;
      bubble.style.width = size + 'px';
      bubble.style.height = size + 'px';
      const offsetX = (Math.random() - 0.5) * 12;
      const offsetY = (Math.random() - 0.5) * 12;
      bubble.style.left = (x - size / 2 + offsetX) + 'px';
      bubble.style.top = (y - size / 2 + offsetY) + 'px';
      document.body.appendChild(bubble);
      setTimeout(() => { bubble.remove(); }, 800);
    }

    function swimMascot(targetLeft, targetTop, instant = false) {
      const avatarEl = document.getElementById('pb-avatar');
      if (!avatarEl || !host) return;

      const currentLeft = parseFloat(host.style.left) || -999;
      const currentTop  = parseFloat(host.style.top)  || -999;

      // Snap without transition on first step or instant moves
      if (instant || isFirstStep) {
        isFirstStep = false;
        host.style.setProperty('transition', 'none', 'important');
        host.style.setProperty('position', 'fixed', 'important');
        host.style.setProperty('bottom', 'auto', 'important');
        host.style.setProperty('right', 'auto', 'important');
        host.style.top  = targetTop  + 'px';
        host.style.left = targetLeft + 'px';
        void host.offsetWidth;
        host.style.removeProperty('transition');
        return;
      }

      if (Math.abs(currentLeft - targetLeft) < 4 && Math.abs(currentTop - targetTop) < 4) {
        return;
      }

      avatarEl.classList.add('pb-swim-active');
      // Allow CSS transition (set in .pb-walkthrough-mode)
      host.style.setProperty('position', 'fixed', 'important');
      host.style.setProperty('bottom', 'auto', 'important');
      host.style.setProperty('right', 'auto', 'important');
      host.style.top  = targetTop  + 'px';
      host.style.left = targetLeft + 'px';

      // Emit swim bubbles
      const duration = 500;
      const bubbleCount = 4;
      for (let i = 0; i < bubbleCount; i++) {
        setTimeout(() => {
          if (!avatarEl.classList.contains('pb-swim-active')) return;
          const rect = avatarEl.getBoundingClientRect();
          createBubbleParticle(
            rect.left + window.scrollX + rect.width  / 2,
            rect.top  + window.scrollY + rect.height / 2
          );
        }, (duration / bubbleCount) * i);
      }

      setTimeout(() => { avatarEl.classList.remove('pb-swim-active'); }, duration);
    }

    function swimOffAndNavigate(path) {
      const avatar = document.getElementById('pb-avatar');
      const host = document.getElementById('pb-host');
      if (!avatar || !host) {
        window.location.href = path;
        return;
      }

      const rect = host.getBoundingClientRect();
      const hostCenterX = rect.left + rect.width / 2;
      const hostCenterY = rect.top + rect.height / 2;

      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;

      const distLeft = hostCenterX;
      const distRight = viewportWidth - hostCenterX;
      const distTop = hostCenterY;
      const distBottom = viewportHeight - hostCenterY;

      const minDist = Math.min(distLeft, distRight, distTop, distBottom);
      let exitEdge = 'right';
      let targetLeft = window.scrollX + viewportWidth + 150;
      let targetTop = window.scrollY + rect.top;

      if (minDist === distLeft) {
        exitEdge = 'left';
        targetLeft = window.scrollX - rect.width - 150;
        targetTop = window.scrollY + rect.top;
      } else if (minDist === distTop) {
        exitEdge = 'top';
        targetLeft = window.scrollX + rect.left;
        targetTop = window.scrollY - rect.height - 150;
      } else if (minDist === distBottom) {
        exitEdge = 'bottom';
        targetLeft = window.scrollX + rect.left;
        targetTop = window.scrollY + viewportHeight + 150;
      } else {
        exitEdge = 'right';
        targetLeft = window.scrollX + viewportWidth + 150;
        targetTop = window.scrollY + rect.top;
      }

      localStorage.setItem('lure_wt_exit_edge', exitEdge);
      avatar.classList.add('pb-swim-active');

      host.style.setProperty('transition', 'top 0.4s cubic-bezier(0.25, 1, 0.5, 1), left 0.4s cubic-bezier(0.25, 1, 0.5, 1)', 'important');
      host.style.setProperty('position', 'fixed', 'important');
      host.style.top = targetTop + 'px';
      host.style.left = targetLeft + 'px';

      for (let i = 0; i < 3; i++) {
        setTimeout(() => {
          const r = avatar.getBoundingClientRect();
          createBubbleParticle(r.left + window.scrollX + r.width / 2, r.top + window.scrollY + r.height / 2);
        }, 100 * i);
      }

      setTimeout(() => {
        window.location.href = path;
      }, 350);
    }

    let wtRepositionInterval = null;
    let lastTargetLeft = null;
    let lastTargetTop = null;
    let lastTargetWidth = null;
    let lastTargetHeight = null;
    let lastScrollX = null;
    let lastScrollY = null;

    function startWtRepositionLoop() {
      if (wtRepositionInterval) clearInterval(wtRepositionInterval);
      wtRepositionInterval = setInterval(() => {
        if (wtActive) {
          repositionWalkthroughElements(true);
        }
      }, 250);
    }

    let unseenCalloutsCount = 0;

    function stopWtRepositionLoop() {
      if (wtRepositionInterval) {
        clearInterval(wtRepositionInterval);
        wtRepositionInterval = null;
      }
      lastTargetLeft = null;
      lastTargetTop = null;
      lastTargetWidth = null;
      lastTargetHeight = null;
      lastScrollX = null;
      lastScrollY = null;
    }

    function repositionWalkthroughElements(isPageScroll = false) {
      if (!wtActive || wtCurrentStep < 0 || wtCurrentStep >= wtSteps.length) return;
      const step = wtSteps[wtCurrentStep];

      // Resolve the target element (dashboard empty-state override)
      let currentTargetId = step.targetId;
      const onDashboard = window.location.pathname.startsWith('/dashboard');
      const emptyStateActive = document.getElementById('no-campaigns-card') &&
            document.getElementById('no-campaigns-card').style.display !== 'none';
      if (onDashboard && emptyStateActive) {
        if (currentTargetId === 'wt-dashboard-view' || currentTargetId === 'mainTrendChart') {
          currentTargetId = 'no-campaigns-card';
        }
      }

      const targetEl = document.getElementById(currentTargetId);
      let highlighter = document.getElementById('pb-wt-highlighter');

      // No target → fall back to bottom-right corner
      if (!targetEl) {
        if (highlighter) highlighter.style.display = 'none';
        host.style.setProperty('position', 'fixed', 'important');
        host.style.setProperty('top', 'auto', 'important');
        host.style.setProperty('left', 'auto', 'important');
        host.style.setProperty('bottom', '24px', 'important');
        host.style.setProperty('right', '24px', 'important');
        avatar.classList.remove('pb-face-left');
        host.classList.remove('pb-direction-left');
        host.classList.add('pb-direction-right');
        return;
      }

      // Wrong page → hide and bail
      const currentPath = window.location.pathname.replace(/\/$/, '') || '/';
      const targetPath  = step.path.split('?')[0].replace(/\/$/, '') || '/';
      if (currentPath !== targetPath) {
        if (highlighter) highlighter.style.display = 'none';
        const bubbleEl = document.getElementById('pb-wt-bubble');
        if (bubbleEl) bubbleEl.style.display = 'none';
        return;
      }

      const rect = targetEl.getBoundingClientRect();
      const currentScrollX = window.scrollX;
      const currentScrollY = window.scrollY;

      // Layout caching optimization: bypass positioning if no coordinates/size/scroll changed
      if (
        rect.left === lastTargetLeft &&
        rect.top === lastTargetTop &&
        rect.width === lastTargetWidth &&
        rect.height === lastTargetHeight &&
        currentScrollX === lastScrollX &&
        currentScrollY === lastScrollY
      ) {
        return;
      }

      lastTargetLeft = rect.left;
      lastTargetTop = rect.top;
      lastTargetWidth = rect.width;
      lastTargetHeight = rect.height;
      lastScrollX = currentScrollX;
      lastScrollY = currentScrollY;

      // Update highlighter (fixed, viewport-relative)
      if (!highlighter) {
        highlighter = document.createElement('div');
        highlighter.id = 'pb-wt-highlighter';
        highlighter.style.cssText = [
          'position:fixed', 'pointer-events:none', 'box-sizing:border-box',
          'border-radius:12px', 'border:2px solid var(--primary)',
          'box-shadow:0 0 0 4px rgba(6,182,212,0.18),0 0 24px rgba(6,182,212,0.35)',
          'z-index:19999', 'transition:all 0.2s ease-out'
        ].join(';');
        document.body.appendChild(highlighter);
      }
      highlighter.style.display = 'block';
      highlighter.style.position = 'fixed';
      highlighter.style.top    = (rect.top    - 5) + 'px';
      highlighter.style.left   = (rect.left   - 5) + 'px';
      highlighter.style.width  = (rect.width  + 10) + 'px';
      highlighter.style.height = (rect.height + 10) + 'px';

      const vw        = window.innerWidth;
      const vh        = window.innerHeight;
      const margin    = 16;
      const mascotW   = 110;
      const bubbleW   = 320;
      const gap       = 10;
      const hostW     = mascotW + gap + bubbleW;   // ~440px
      const bubbleEl  = document.getElementById('pb-wt-bubble');
      const hostH     = bubbleEl ? Math.max(bubbleEl.offsetHeight, 160) : 200;

      // Mobile: stick below the element
      if (vw <= 768) {
        if (bubbleEl) bubbleEl.classList.add('pb-mobile-no-arrow');
        const cardLeft = Math.max(margin, (vw - bubbleW) / 2);
        const cardTop  = Math.min(rect.bottom + gap, vh - hostH - margin);
        swimMascot(cardLeft, cardTop);
        return;
      }
      if (bubbleEl) bubbleEl.classList.remove('pb-mobile-no-arrow');

      // Compute available space on each side (viewport-relative)
      const spaceRight  = vw - rect.right;
      const spaceLeft   = rect.left;
      const spaceBottom = vh - rect.bottom;
      const spaceTop    = rect.top;

      // Pick the side with the most room for the full host group
      let bestSide = 'right';
      let maxSpace = spaceRight;

      if (spaceLeft > maxSpace && spaceLeft >= hostW + margin) {
        bestSide = 'left';
        maxSpace = spaceLeft;
      }
      if (spaceBottom > maxSpace) {
        bestSide = 'bottom';
        maxSpace = spaceBottom;
      }
      if (spaceTop > maxSpace) {
        bestSide = 'top';
        maxSpace = spaceTop;
      }

      // Force right if it fits (most common layout)
      if (spaceRight >= hostW + margin) bestSide = 'right';

      let hostLeft = 0;
      let hostTop  = 0;

      if (bestSide === 'right') {
        hostLeft = rect.right + gap;
        hostTop  = rect.top + (rect.height - hostH) / 2;
      } else if (bestSide === 'left') {
        hostLeft = rect.left - hostW - gap;
        hostTop  = rect.top + (rect.height - hostH) / 2;
      } else if (bestSide === 'top') {
        hostLeft = rect.left + (rect.width - hostW) / 2;
        hostTop  = rect.top - hostH - gap;
      } else {
        hostLeft = rect.left + (rect.width - hostW) / 2;
        hostTop  = rect.bottom + gap;
      }

      // Face direction
      const targetCx = rect.left + rect.width / 2;
      const hostCx   = hostLeft + hostW / 2;
      if (targetCx < hostCx) {
        avatar.classList.add('pb-face-left');
        host.classList.remove('pb-direction-right');
        host.classList.add('pb-direction-left');
      } else {
        avatar.classList.remove('pb-face-left');
        host.classList.remove('pb-direction-left');
        host.classList.add('pb-direction-right');
      }

      // Clamp to viewport with margin
      const cardLeft = Math.max(margin, Math.min(hostLeft, vw - hostW - margin));
      const cardTop  = Math.max(margin, Math.min(hostTop,  vh - hostH - margin));

    const TOUR_METADATA = {
      core_workflow: {
        name: "The Full Simulation Loop (Flagship)",
        desc: "Follow the complete end-to-end simulation lifecycle: launch a campaign, trace target reactions, and review AI analytics reports.",
        icon: "ti ti-refresh",
        color: "var(--primary)",
        category: "Core Simulator Tours"
      },
      getting_started: {
        name: "Getting Started (Recommended)",
        desc: "The essential 9-step onboarding walkthrough covering the sandbox terminal, scenario formulation, and real-time dashboard analytics.",
        icon: "ti ti-compass",
        color: "var(--primary)",
        category: "Core Simulator Tours"
      },
      campaign_launch: {
        name: "Simulating Campaigns Guide",
        desc: "A 3-step walkthrough on executing security terminal queries and setting up active simulation campaigns.",
        icon: "ti ti-terminal-2",
        color: "var(--warning)",
        category: "Feature Deep-Dives"
      },
      lure_generation: {
        name: "AI Email Generation Guide",
        desc: "A 3-step tour showing how Lure drafts personalized phishing pretexts and calculates threat bait scores.",
        icon: "ti ti-mail",
        color: "var(--primary)",
        category: "Feature Deep-Dives"
      },
      attack_analysis: {
        name: "Attack Path & Risk Analyzer Guide",
        desc: "A 2-step overview of attack path visualization mapping and organizational threat profile reporting.",
        icon: "ti ti-git-commit",
        color: "var(--danger)",
        category: "Feature Deep-Dives"
      },
      tool_threat_analyzer: {
        name: "Threat Analyzer Tour",
        desc: "A 4-step walkthrough of pasting and auditing raw email copy for phishing red flags.",
        icon: "ti ti-eye",
        color: "var(--warning)",
        category: "Standalone Forensic Tools"
      },
      tool_header_analyzer: {
        name: "Header Analyzer Tour",
        desc: "A 4-step walkthrough of tracing technical email header hop paths and sender authentication records.",
        icon: "ti ti-route",
        color: "var(--primary)",
        category: "Standalone Forensic Tools"
      },
      tool_url_decoder: {
        name: "URL Decoder Tour",
        desc: "A 4-step guide to decoding redirect loops, expanding short links, and rendering page previews.",
        icon: "ti ti-link",
        color: "var(--warning)",
        category: "Standalone Forensic Tools"
      },
      tool_password_breach: {
        name: "Password & Leak Tour",
        desc: "A 4-step inspection of local password complexity and email address database leak scans.",
        icon: "ti ti-shield-lock",
        color: "var(--danger)",
        category: "Standalone Forensic Tools"
      }
    };

    window.renderToursList = function() {
      const containers = document.querySelectorAll('.pb-wt-guide-list');
      if (containers.length === 0) return;
      
      loadVisitorProfile();
      
      const categories = [
        "Core Simulator Tours",
        "Feature Deep-Dives",
        "Standalone Forensic Tools"
      ];
      
      let html = '';
      
      categories.forEach(cat => {
        // Add category header
        html += `<div style="font-family:var(--mono); font-size:0.65rem; color:var(--text-secondary,#8CA0B3); text-transform:uppercase; margin: 16px 0 6px 4px; letter-spacing:0.5px;">${cat}</div>`;
        
        // Find tours in this category
        for (const key in TOUR_METADATA) {
          const meta = TOUR_METADATA[key];
          if (meta.category !== cat) continue;
          
          const steps = WALKTHROUGH_CONFIGS[key] || [];
          const totalSteps = steps.length;
          
          const isCompleted = visitorProfile.completedTours && visitorProfile.completedTours[key];
          const currentStep = visitorProfile.tourProgress ? visitorProfile.tourProgress[key] : undefined;
          const isInProgress = !isCompleted && currentStep !== undefined && currentStep >= 0;
          
          let badgeHtml = '';
          let cardStyle = '';
          if (isCompleted) {
            badgeHtml = `<span class="pb-tour-badge completed" style="font-size: 0.6rem; font-weight: 700; color: var(--success,#34D399); background: color-mix(in srgb, var(--success,#34D399) 10%, transparent); padding: 2px 6px; border-radius: 4px; border: 1px solid color-mix(in srgb, var(--success,#34D399) 20%, transparent); display: flex; align-items: center; gap: 3px; flex-shrink: 0;"><i class="ti ti-check"></i> Done</span>`;
          } else if (isInProgress) {
            badgeHtml = `<span class="pb-tour-badge progress" style="font-size: 0.6rem; font-weight: 700; color: var(--warning); background: color-mix(in srgb, var(--warning) 10%, transparent); padding: 2px 6px; border-radius: 4px; border: 1px solid color-mix(in srgb, var(--warning) 20%, transparent); display: flex; align-items: center; gap: 3px; flex-shrink: 0;"><i class="ti ti-progress"></i> Step ${currentStep + 1}/${totalSteps}</span>`;
          }
          
          if (key === 'getting_started') {
            cardStyle = `border-color: var(--primary); background: color-mix(in srgb, var(--primary) 6%, transparent);`;
          }
          
          html += `
            <div class="pb-wt-guide-card" onclick="startWalkthrough('${key}')" style="${cardStyle}">
              <div class="pb-wt-guide-icon" style="color: ${meta.color};"><i class="${meta.icon}"></i></div>
              <div class="pb-wt-guide-info">
                <div class="pb-wt-guide-name" style="${key === 'getting_started' ? 'font-weight:700; color:var(--primary);' : ''}">
                  ${meta.name} (${totalSteps} steps)
                </div>
                <div class="pb-wt-guide-desc">${meta.desc}</div>
              </div>
              <div style="display:flex; align-items:center; gap:8px;">
                ${badgeHtml}
                <button class="pb-wt-guide-go" style="${key === 'getting_started' ? 'background: var(--primary); color: #000; padding: 4px; border-radius: 4px;' : ''}"><i class="ti ti-arrow-right"></i></button>
              </div>
            </div>
          `;
        }
      });
      
      containers.forEach(container => {
        container.innerHTML = html;
      });
    };

    window.startWalkthrough = function(pageKey) {
      const config = WALKTHROUGH_CONFIGS[pageKey];
      if (!config || config.length === 0) return;
      initGateListeners();

      wtSteps = config;
      wtCurrentStep = 0;
      wtCurrentPage = pageKey;
      wtActive = true;

      // Save state in localStorage to track it across reloads
      localStorage.setItem('pb_wt_active', 'true');
      localStorage.setItem('pb_wt_page_key', pageKey);
      localStorage.setItem('pb_wt_step_idx', '0');

      // Update progress in visitorProfile
      loadVisitorProfile();
      if (!visitorProfile.tourProgress) {
        visitorProfile.tourProgress = {};
      }
      if (!visitorProfile.completedTours[pageKey]) {
        visitorProfile.tourProgress[pageKey] = 0;
      }
      saveVisitorProfile();
      if (window.renderToursList) renderToursList();

      // Close the takeover modal
      inlineSec.style.display = 'none';
      expanded = false;

      // Prepare host walkthrough mode
      host.classList.add('pb-walkthrough-mode');
      const bubbleEl = document.getElementById('pb-wt-bubble');
      if (bubbleEl) bubbleEl.style.display = 'block';

      resizeHandler = () => repositionWalkthroughElements(false);
      scrollHandler = () => repositionWalkthroughElements(true);
      window.addEventListener('resize', resizeHandler);
      window.addEventListener('scroll', scrollHandler, { capture: true, passive: true });
      startWtRepositionLoop();

      // Check if we need to redirect immediately
      const currentPath = window.location.pathname.replace(/\/$/, '') || '/';
      const targetPath = config[0].path.split('?')[0].replace(/\/$/, '') || '/';

      if (currentPath !== targetPath) {
        window.location.href = config[0].path;
      } else {
        renderWalkthroughStep();
      }
    };

    function renderBubbleContent(step, isSkipped = false) {
      const bubbleEl = document.getElementById('pb-wt-bubble');
      if (!bubbleEl) return;

      const isLastStep = (wtCurrentStep === wtSteps.length - 1);
      
      let dotsHtml = '<div style="display:flex; gap:4px; align-items:center; margin-top:4px;">';
      for (let i = 0; i < wtSteps.length; i++) {
        const isCurrent = (i === wtCurrentStep);
        dotsHtml += `<span style="width:6px; height:6px; border-radius:50%; border:1px solid var(--primary); background:${isCurrent ? 'var(--primary)' : 'transparent'}; display:inline-block;"></span>`;
      }
      dotsHtml += '</div>';

      const esc = (s) => (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

      // Gating instruction text overrides based on step index
      let gatePromptText = "Complete the task on the screen to unlock the next step!";
      if (wtCurrentPage === 'getting_started') {
        if (wtCurrentStep === 0) gatePromptText = "Action Required: Type 'query demo-corp.com' and press Enter in the terminal!";
        if (wtCurrentStep === 1) gatePromptText = "Action Required: Click 'CEO Fraud' or another pretext scenario above to generate an email!";
        if (wtCurrentStep === 2) gatePromptText = "Action Required: Enter a campaign name (at least 3 characters) above!";
        if (wtCurrentStep === 3) gatePromptText = "Action Required: Select one of the pretext cards above!";
        if (wtCurrentStep === 4) gatePromptText = "Action Required: Select a delivery mode above (e.g. Sandbox Test)!";
        if (wtCurrentStep === 5) gatePromptText = "Action Required: Check the 'Authorization Required' checkbox below!";
      }

      bubbleEl.innerHTML = `
        <div style="display:flex; flex-direction:column; gap:12px;">
          <!-- Header title & counter -->
          <div style="display:flex; flex-direction:column; border-bottom: 1px solid rgba(255,255,255,0.06); padding-bottom:6px;">
            <div style="display:flex; justify-content:space-between; align-items:center; width:100%;">
              <span style="font-family:var(--sans); font-size:0.75rem; font-weight:700; color:${isSkipped ? 'var(--warning)' : 'var(--primary)'};">
                ${esc(step.title)}
              </span>
              <span style="font-family:var(--mono); font-size:0.58rem; color:var(--text-secondary,#94A3B8);">
                Step ${wtCurrentStep + 1} of ${wtSteps.length}
              </span>
            </div>
            ${dotsHtml}
          </div>

          <!-- Dialogue bubble with speech text -->
          <div style="display:flex; gap:12px; align-items:flex-start;">
            <div style="flex:1;">
              <p style="font-size:0.7rem; color:var(--text-primary,#F0F4FF); line-height:1.45; margin:0;">
                ${esc(step.text)}
              </p>
              
              <!-- Gate visual feedback badge -->
              <div class="pb-gate-prompt" style="display:none; align-items:center; gap:6px; background:rgba(6, 182, 212, 0.08); border:1px dashed rgba(6, 182, 212, 0.35); padding:6px 8px; border-radius:6px; font-size:0.58rem; color:var(--primary); line-height:1.3; font-weight:600; margin-top:8px; animation: pbPulse 1.2s infinite alternate;">
                <i class="ti ti-fingerprint" style="font-size:0.75rem; color:var(--primary);"></i>
                <span>${esc(gatePromptText)}</span>
              </div>
            </div>
          </div>

          <!-- Action buttons row -->
          <div style="display:flex; flex-direction:column; gap:8px; margin-top:4px;">
            <div style="display:flex; justify-content:space-between; gap:8px;">
              <button class="pb-action-btn" onclick="prevWalkthroughStep()" ${wtCurrentStep === 0 ? 'disabled class="pb-disabled"' : ''} style="flex:1; padding:6px 10px; font-size:0.62rem; margin: 0;">
                <i class="ti ti-arrow-left"></i> Back
              </button>
              <button class="pb-action-btn" onclick="repeatWalkthroughStep()" style="flex:1; padding:6px 10px; font-size:0.62rem; margin: 0;">
                <i class="ti ti-refresh"></i> Repeat
              </button>
              <button class="pb-action-btn pb-next-btn" onclick="nextWalkthroughStepBtn()" style="flex:2; padding:6px 10px; font-size:0.62rem; font-weight:bold; background:var(--primary); color:var(--text-inverse,#0A1420); margin: 0;">
                ${isLastStep ? 'Finish' : 'Next <i class="ti ti-arrow-right"></i>'}
              </button>
            </div>
            <div style="display:flex; justify-content:space-between; align-items:center; border-top:1px solid rgba(255,255,255,0.04); padding-top:6px; font-size:0.6rem;">
              <button class="pb-action-btn" onclick="exitWalkthrough()" style="padding:2px 6px; font-size:0.58rem; background:transparent; opacity:0.6; margin: 0;">
                Skip All
              </button>
              <button class="pb-action-btn" onclick="nextWalkthroughStepBtn()" style="padding:2px 6px; font-size:0.58rem; background:transparent; opacity:0.6; margin: 0;">
                Skip Step
              </button>
            </div>
          </div>
        </div>
      `;
    }

    function renderWalkthroughStep() {
      if (!wtActive || wtCurrentStep < 0 || wtCurrentStep >= wtSteps.length) return;

      // Update progress in visitorProfile
      loadVisitorProfile();
      if (!visitorProfile.tourProgress) {
        visitorProfile.tourProgress = {};
      }
      if (!visitorProfile.completedTours[wtCurrentPage]) {
        visitorProfile.tourProgress[wtCurrentPage] = wtCurrentStep;
      }
      saveVisitorProfile();
      if (window.renderToursList) renderToursList();
      
      // Reset position caches to force immediate computation on step load
      lastTargetLeft = null;
      lastTargetTop = null;
      lastTargetWidth = null;
      lastTargetHeight = null;
      lastScrollX = null;
      lastScrollY = null;
      
      const step = wtSteps[wtCurrentStep];
      
      const bubbleEl = document.getElementById('pb-wt-bubble');
      if (bubbleEl) bubbleEl.style.display = 'block';

      // Remove any existing highlights
      document.querySelectorAll('.pb-highlight-active').forEach(el => {
        el.classList.remove('pb-highlight-active');
      });

      let searchAttempts = 0;
      const maxSearchAttempts = 15; // 3 seconds total

      function tryHighlightAndPosition() {
        if (!wtActive || wtCurrentStep >= wtSteps.length) return;
        const s = wtSteps[wtCurrentStep];
        
        let currentTargetId = s.targetId;
        const onDashboard = window.location.pathname.startsWith('/dashboard');
        const emptyStateActive = document.getElementById('no-campaigns-card') && document.getElementById('no-campaigns-card').style.display !== 'none';
        
        // Empty state redirect details override
        if (onDashboard && emptyStateActive) {
          if (currentTargetId === 'wt-dashboard-view' || currentTargetId === 'mainTrendChart') {
            currentTargetId = 'no-campaigns-card';
          }
        }

        const targetEl = document.getElementById(currentTargetId);

        if (targetEl) {
          document.querySelectorAll('.pb-highlight-active').forEach(el => {
            el.classList.remove('pb-highlight-active');
          });
          targetEl.classList.add('pb-highlight-active');
          // Scroll instantly, temporarily bypassing global smooth scrolling styles
          const htmlStyle = document.documentElement.style;
          const bodyStyle = document.body.style;
          const originalHtmlScroll = htmlStyle.scrollBehavior;
          const originalBodyScroll = bodyStyle.scrollBehavior;
          
          htmlStyle.scrollBehavior = 'auto';
          bodyStyle.scrollBehavior = 'auto';
          
          targetEl.scrollIntoView({ behavior: 'auto', block: 'center' });
          
          // Force layout reflow to apply scroll change immediately
          void targetEl.offsetHeight;
          
          htmlStyle.scrollBehavior = originalHtmlScroll;
          bodyStyle.scrollBehavior = originalBodyScroll;
          
          // Reposition immediately using correct coordinates, with a safety layout delay
          repositionWalkthroughElements();
          setTimeout(repositionWalkthroughElements, 100);

          if (onDashboard && emptyStateActive) {
            let adaptedText = s.text;
            let adaptedTitle = s.title;
            if (wtCurrentStep === 6) {
              adaptedTitle = "Dashboard is Ready";
              adaptedText = "Once you launch a simulation, your campaign metrics will appear here. Right now, it's empty because you haven't started one yet!";
            } else if (wtCurrentStep === 7) {
              adaptedTitle = "Track Simulation Trends";
              adaptedText = "This trend chart will graph your click-rates over time. Let's get you set up to create your first simulation campaign so you can see it in action!";
            }
            renderBubbleContent({ title: adaptedTitle, text: adaptedText }, false);
          } else {
            renderBubbleContent(s, false);
          }
          updateWalkthroughGate();
        } else {
          if (searchAttempts < maxSearchAttempts) {
            searchAttempts++;
            setTimeout(tryHighlightAndPosition, 200);
          } else {
            // Skinned skipped fallback state
            repositionWalkthroughElements(); // handles null target
            const skippedStep = {
              title: `Scanning for ${s.title}...`,
              text: `I couldn't find that section on the screen, but let's keep swimming! You can skip this step or hit Next to continue.`
            };
            renderBubbleContent(skippedStep, true);
          }
        }
      }

      tryHighlightAndPosition();
    }

        window.repeatWalkthroughStep = function() {
      if (!wtActive || wtCurrentStep < 0 || wtCurrentStep >= wtSteps.length) return;
      const step = wtSteps[wtCurrentStep];
      const targetEl = document.getElementById(step.targetId);
      if (targetEl) {
        targetEl.classList.remove('pb-highlight-active');
        void targetEl.offsetWidth; // force reflow
        targetEl.classList.add('pb-highlight-active');
        targetEl.scrollIntoView({ behavior: 'auto', block: 'nearest' });
        repositionWalkthroughElements();
      }
    };

    window.nextWalkthroughStepBtn = function() {
      if (wtCurrentStep === wtSteps.length - 1) {
        finishWalkthrough();
        return;
      }
      
      const step = wtSteps[wtCurrentStep];
      
      // Increment step
      wtCurrentStep++;
      localStorage.setItem('pb_wt_step_idx', wtCurrentStep.toString());

      // Check if we need redirection
      if (step.redirectPath) {
        swimOffAndNavigate(step.redirectPath);
      } else {
        const nextStep = wtSteps[wtCurrentStep];
        const currentPath = window.location.pathname.replace(/\/$/, '') || '/';
        const targetPath = nextStep.path.split('?')[0].replace(/\/$/, '') || '/';

        if (currentPath !== targetPath) {
          swimOffAndNavigate(nextStep.path);
        } else {
          renderWalkthroughStep();
        }
      }
    };

    window.prevWalkthroughStep = function() {
      if (wtCurrentStep > 0) {
        wtCurrentStep--;
        localStorage.setItem('pb_wt_step_idx', wtCurrentStep.toString());

        const prevStep = wtSteps[wtCurrentStep];
        const currentPath = window.location.pathname.replace(/\/$/, '') || '/';
        const targetPath = prevStep.path.split('?')[0].replace(/\/$/, '') || '/';

        if (currentPath !== targetPath) {
          swimOffAndNavigate(prevStep.path);
        } else {
          renderWalkthroughStep();
        }
      }
    };

    window.exitWalkthrough = function() {
      cleanupWalkthrough();
    };

    window.finishWalkthrough = function() {
      loadVisitorProfile();
      visitorProfile.hasCompletedTour = true;
      if (!visitorProfile.completedTours) {
        visitorProfile.completedTours = {};
      }
      visitorProfile.completedTours[wtCurrentPage] = true;
      if (visitorProfile.tourProgress) {
        delete visitorProfile.tourProgress[wtCurrentPage];
      }
      saveVisitorProfile();
      if (window.renderToursList) renderToursList();
      cleanupWalkthrough();
      if (wtCurrentPage === 'getting_started') {
        window.location.href = '/logout?completed_tour=true';
      }
    };

    function cleanupWalkthrough() {
      wtActive = false;
      isFirstStep = true;
      localStorage.removeItem('pb_wt_active');
      localStorage.removeItem('pb_wt_page_key');
      localStorage.removeItem('pb_wt_step_idx');
      
      document.querySelectorAll('.pb-highlight-active').forEach(el => {
        el.classList.remove('pb-highlight-active');
      });

      const highlighter = document.getElementById('pb-wt-highlighter');
      if (highlighter) highlighter.style.display = 'none';

      // Restore host position and classes
      host.classList.remove('pb-walkthrough-mode');
      host.classList.remove('pb-direction-left');
      host.classList.remove('pb-direction-right');
      avatar.classList.remove('pb-face-left');

      host.style.removeProperty('position');
      host.style.removeProperty('top');
      host.style.removeProperty('left');
      host.style.removeProperty('bottom');
      host.style.removeProperty('right');
      host.style.removeProperty('display');

      const bubbleEl = document.getElementById('pb-wt-bubble');
      if (bubbleEl) {
        bubbleEl.style.display = 'none';
        bubbleEl.innerHTML = '';
      }

      stopWtRepositionLoop();

      if (resizeHandler) {
        window.removeEventListener('resize', resizeHandler);
      }
      if (scrollHandler) {
        window.removeEventListener('scroll', scrollHandler, { capture: true });
      }
    }

    // Resume walkthrough logic on page load
    function resumeWalkthroughOnLoad() {
      const active = localStorage.getItem('pb_wt_active') === 'true';
      if (active) {
        const pageKey = localStorage.getItem('pb_wt_page_key') || 'getting_started';
        const stepIdx = parseInt(localStorage.getItem('pb_wt_step_idx') || '0', 10);
        
        wtCurrentPage = pageKey;
        wtSteps = WALKTHROUGH_CONFIGS[pageKey];
        wtCurrentStep = stepIdx;
        wtActive = true;

        // Sync progress in profile
        loadVisitorProfile();
        if (!visitorProfile.tourProgress) {
          visitorProfile.tourProgress = {};
        }
        if (!visitorProfile.completedTours[pageKey]) {
          visitorProfile.tourProgress[pageKey] = stepIdx;
        }
        saveVisitorProfile();
        
        expanded = false;
        inlineSec.classList.remove('pb-walkthrough-active');
        inlineSec.style.display = 'none';
        host.classList.add('pb-walkthrough-mode');
        
        const bubbleEl = document.getElementById('pb-wt-bubble');
        if (bubbleEl) bubbleEl.style.display = 'block';

        resizeHandler = () => repositionWalkthroughElements(false);
        scrollHandler = () => repositionWalkthroughElements(true);
        window.addEventListener('resize', resizeHandler);
        window.addEventListener('scroll', scrollHandler, { capture: true, passive: true });
        startWtRepositionLoop();
        initGateListeners();

        const exitEdge = localStorage.getItem('lure_wt_exit_edge');
        if (exitEdge) {
          localStorage.removeItem('lure_wt_exit_edge');
          isFirstStep = false; // Set to false to allow smooth swimming in
          
          const viewportWidth = window.innerWidth;
          const viewportHeight = window.innerHeight;
          let startLeft = viewportWidth + 150;
          let startTop = viewportHeight / 2;
          
          if (exitEdge === 'left') {
            startLeft = -450;
            startTop = viewportHeight / 2;
          } else if (exitEdge === 'top') {
            startLeft = viewportWidth / 2;
            startTop = -350;
          } else if (exitEdge === 'bottom') {
            startLeft = viewportWidth / 2;
            startTop = viewportHeight + 150;
          }
          
          host.style.setProperty('position', 'fixed', 'important');
          host.style.left = startLeft + 'px';
          host.style.top = startTop + 'px';
          host.style.setProperty('bottom', 'auto', 'important');
          host.style.setProperty('right', 'auto', 'important');
          host.style.transition = 'none';
          
          setTimeout(() => {
            host.style.transition = '';
            renderWalkthroughStep();
          }, 100);
        } else {
          renderWalkthroughStep();
        }
      }
    }

    if (document.readyState !== 'loading') {
      resumeWalkthroughOnLoad();
      if (window.renderToursList) renderToursList();
    } else {
      window.addEventListener('DOMContentLoaded', () => {
        resumeWalkthroughOnLoad();
        if (window.renderToursList) renderToursList();
      });
    }

    /* ================================================================
       Spot the Phish Game Script (Inline/Overlay Mode support)
       ================================================================ */
    let gameRoundsLeft = 3;
    let correctPhishIndex = null;
    let currentPhishTactic = "";
    let currentBaitScore = null;
    let gameScoreCorrect = 0;
    let gameScoreTotal = 0;
    let gameActive = false;

    let ilGameRoundsLeft = 3;
    let ilCorrectPhishIndex = null;
    let ilCurrentPhishTactic = "";
    let ilCurrentBaitScore = null;
    let ilGameScoreCorrect = 0;
    let ilGameScoreTotal = 0;
    let ilGameActive = false;

    async function updateGameStatus() {
      try {
        const res = await fetch("/api/spot-the-phish/status");
        if (res.ok) {
          const j = await res.json();
          if (j.success) {
            gameRoundsLeft = j.rounds_left;
            const limitText = document.getElementById("stp-limit-text");
            if (limitText) {
              if (gameRoundsLeft === 0) {
                limitText.textContent = "0 rounds left today (Come back tomorrow)";
                limitText.style.color = "var(--warning)";
              } else {
                limitText.textContent = `Rounds Left Today: ${gameRoundsLeft} / 3`;
                limitText.style.color = "var(--text-secondary, #94A3B8)";
              }
            }
            const nextBtn = document.getElementById("stp-next-btn");
            if (nextBtn) {
              if (gameRoundsLeft === 0) {
                nextBtn.textContent = "0 rounds left today";
                nextBtn.disabled = true;
                nextBtn.classList.add("pb-disabled");
              } else {
                nextBtn.textContent = "Next Round";
                nextBtn.disabled = false;
                nextBtn.classList.remove("pb-disabled");
              }
            }
          }
        }
      } catch (e) {
        console.error("Failed to fetch game status", e);
      }
    }

    async function updateInlineGameStatus() {
      try {
        const res = await fetch("/api/spot-the-phish/status");
        if (res.ok) {
          const j = await res.json();
          if (j.success) {
            ilGameRoundsLeft = j.rounds_left;
            const limitText = document.getElementById("stp-il-limit-text");
            if (limitText) {
              if (ilGameRoundsLeft === 0) {
                limitText.textContent = "0 rounds left today (Come back tomorrow)";
                limitText.style.color = "var(--warning)";
              } else {
                limitText.textContent = `Rounds Left Today: ${ilGameRoundsLeft} / 3`;
                limitText.style.color = "var(--text-secondary, #94A3B8)";
              }
            }
            const nextBtn = document.getElementById("stp-il-next-btn");
            if (nextBtn) {
              if (ilGameRoundsLeft === 0) {
                nextBtn.textContent = "0 rounds left today";
                nextBtn.disabled = true;
                nextBtn.classList.add("pb-disabled");
              } else {
                nextBtn.textContent = "Next Round";
                nextBtn.disabled = false;
                nextBtn.classList.remove("pb-disabled");
              }
            }
          }
        }
      } catch (e) {
        console.error("Failed to fetch inline game status", e);
      }
    }

    window.stpRender = async function() {
      const con = document.getElementById('stp-pair-container');
      const resEl = document.getElementById('stp-result');
      const nextBtn = document.getElementById('stp-next-btn');
      if (!con) return;

      resEl.style.display = 'none';
      nextBtn.style.display = 'none';
      await updateGameStatus();
      updateMessageAvatar('pb-spotphish-avatar-container', 'idle');

      const dialogueEl = document.getElementById('stp-dialogue-text');
      if (dialogueEl) {
        dialogueEl.innerHTML = 'Two emails below — one legit, one is a phish. <strong style="color:var(--primary);">Click the fake one.</strong>';
      }

      con.innerHTML = `
        <div class="pb-skeleton-wrap" style="display:block; width:100%;">
          <div class="skeleton-block" style="width:80%;height:10px;"></div>
          <div class="skeleton-block" style="width:70%;height:10px;"></div>
        </div>
      `;

      try {
        const res = await fetch("/api/spot-the-phish/generate", { method: "POST" });
        if (res.status === 429) {
          const j = await res.json();
          con.innerHTML = `<div style="color:var(--warning);font-size:0.7rem;text-align:center;">${esc(j.message)}</div>`;
          gameRoundsLeft = 0;
          await updateGameStatus();
          return;
        }
        if (!res.ok) throw new Error("API failed");
        const data = await res.json();
        correctPhishIndex = data.phish_index;
        currentPhishTactic = data.phish_tactic;
        currentBaitScore = data.bait_score;
        gameRoundsLeft = data.rounds_left;

        con.innerHTML = '';
        data.emails.forEach((email, index) => {
          const box = document.createElement('div');
          box.className = 'stp-box';
          box.innerHTML = `
            <div class="stp-box-chrome"><span style="background:#ef4444;"></span><span style="background:#f59e0b;"></span><span style="background:#10b981;"></span></div>
            <div class="stp-box-header">
              <div><span class="stp-lbl">From:</span> ${esc(email.sender_display || email.sender)}</div>
              <div><span class="stp-lbl">Subject:</span> ${esc(email.subject)}</div>
            </div>
            <div class="stp-box-body">${esc(email.body_text)}</div>
          `;
          box.addEventListener('click', () => {
            if (!gameActive) return;
            gameActive = false;
            if (index === correctPhishIndex) {
              box.classList.add('correct');
              resEl.className = 'stp-result phish';
              resEl.style.display = 'block';
              resEl.innerHTML = `<strong>CORRECT! That was a Phish!</strong><br>Tactic: ${esc(currentPhishTactic)}`;
              gameScoreCorrect++;
              updateMessageAvatar('pb-spotphish-avatar-container', 'success', 2500);

              if (dialogueEl) {
                const tacticName = currentPhishTactic ? currentPhishTactic.toLowerCase() : "suspicious cues";
                const template = getRandomVariant(spotCorrectPool, 'spot_correct');
                dialogueEl.innerHTML = template.replace('{tactic}', '<strong>' + esc(tacticName) + '</strong>');
              }
            } else {
              box.classList.add('wrong');
              resEl.className = 'stp-result';
              resEl.style.display = 'block';
              resEl.style.background = 'var(--danger-dim)';
              resEl.style.color = 'var(--danger)';
              resEl.innerHTML = `<strong>INCORRECT! That was Legitimate!</strong><br>The other one was the phish.`;
              updateMessageAvatar('pb-spotphish-avatar-container', 'error', 2500);

              if (dialogueEl) {
                dialogueEl.innerHTML = getRandomVariant(spotIncorrectPool, 'spot_incorrect');
              }
            }
            gameScoreTotal++;
            document.getElementById('stp-score').textContent = gameScoreCorrect;
            document.getElementById('stp-total').textContent = gameScoreTotal;
            nextBtn.style.display = 'inline-flex';
            repositionPanel();
          });
          con.appendChild(box);
        });
        gameActive = true;
      } catch (e) {
        con.innerHTML = `<div style="color:var(--danger);font-size:0.7rem;">Failed to load game round.</div>`;
      }
      repositionPanel();
    };

    window.stpInlineRender = async function() {
      const con = document.getElementById('stp-il-pair-container');
      const resEl = document.getElementById('stp-il-result');
      const nextBtn = document.getElementById('stp-il-next-btn');
      if (!con) return;

      resEl.style.display = 'none';
      if (nextBtn) nextBtn.style.display = 'none';
      await updateInlineGameStatus();
      updateMessageAvatar('pb-spotphish-il-avatar-container', 'idle');

      const dialogueEl = document.getElementById('stp-il-dialogue-text');
      if (dialogueEl) {
        dialogueEl.innerHTML = 'Two freshly generated emails below. One is legitimate, one is a phishing attempt. <strong style="color:var(--primary);">Click the fake one.</strong>';
      }

      con.innerHTML = `
        <div class="pb-skeleton-wrap" style="display:block; width:100%;">
          <div class="skeleton-block" style="width:80%;height:10px;"></div>
          <div class="skeleton-block" style="width:70%;height:10px;"></div>
        </div>
      `;

      try {
        const res = await fetch("/api/spot-the-phish/generate", { method: "POST" });
        if (res.status === 429) {
          const j = await res.json();
          con.innerHTML = `<div style="color:var(--warning);font-size:0.7rem;text-align:center;">${esc(j.message)}</div>`;
          ilGameRoundsLeft = 0;
          await updateInlineGameStatus();
          return;
        }
        if (!res.ok) throw new Error("API failed");
        const data = await res.json();
        ilCorrectPhishIndex = data.phish_index;
        ilCurrentPhishTactic = data.phish_tactic;
        ilCurrentBaitScore = data.bait_score;
        ilGameRoundsLeft = data.rounds_left;

        con.innerHTML = '';
        data.emails.forEach((email, index) => {
          const box = document.createElement('div');
          box.className = 'stp-box';
          box.innerHTML = `
            <div class="stp-box-chrome"><span style="background:#ef4444;"></span><span style="background:#f59e0b;"></span><span style="background:#10b981;"></span></div>
            <div class="stp-box-header">
              <div><span class="stp-lbl">From:</span> ${esc(email.sender_display || email.sender)}</div>
              <div><span class="stp-lbl">Subject:</span> ${esc(email.subject)}</div>
            </div>
            <div class="stp-box-body">${esc(email.body_text)}</div>
          `;
          box.addEventListener('click', () => {
            if (!ilGameActive) return;
            ilGameActive = false;
            if (index === ilCorrectPhishIndex) {
              box.classList.add('correct');
              resEl.className = 'stp-result phish';
              resEl.style.display = 'block';
              resEl.innerHTML = `<strong>CORRECT! That was a Phish!</strong><br>Tactic: ${esc(ilCurrentPhishTactic)}`;
              ilGameScoreCorrect++;
              updateMessageAvatar('pb-spotphish-il-avatar-container', 'success', 2500);

              if (dialogueEl) {
                const tacticName = ilCurrentPhishTactic ? ilCurrentPhishTactic.toLowerCase() : "suspicious cues";
                const template = getRandomVariant(spotCorrectPool, 'spot_correct');
                dialogueEl.innerHTML = template.replace('{tactic}', '<strong>' + esc(tacticName) + '</strong>');
              }
            } else {
              box.classList.add('wrong');
              resEl.className = 'stp-result';
              resEl.style.display = 'block';
              resEl.style.background = 'var(--danger-dim)';
              resEl.style.color = 'var(--danger)';
              resEl.innerHTML = `<strong>INCORRECT! That was Legitimate!</strong><br>The other one was the phish.`;
              updateMessageAvatar('pb-spotphish-il-avatar-container', 'error', 2500);

              if (dialogueEl) {
                dialogueEl.innerHTML = getRandomVariant(spotIncorrectPool, 'spot_incorrect');
              }
            }
            ilGameScoreTotal++;
            document.getElementById('stp-il-score').textContent = ilGameScoreCorrect;
            document.getElementById('stp-il-total').textContent = ilGameScoreTotal;
            if (nextBtn) nextBtn.style.display = 'inline-flex';
          });
          con.appendChild(box);
        });
        ilGameActive = true;
      } catch (e) {
        con.innerHTML = `<div style="color:var(--danger);font-size:0.7rem;">Failed to load game round.</div>`;
      }
    };

    window.stpNext = function() {
      stpRender();
    };

    window.stpInlineNext = function() {
      stpInlineRender();
    };

    // Attach tab show triggers to bootstrap games
    panel.querySelector('.pb-tab-btn[data-tab="spotphish"]').addEventListener('click', () => {
      stpRender();
    });
    inlineSec.querySelector('.pb-tab-btn[data-tab="il-spotphish"]').addEventListener('click', () => {
      stpInlineRender();
    });

    /* ================================================================
       Risk Score calculations
       ================================================================ */
    window.rsCalc = function() {
      const ind = document.querySelector('input[name="rs-ind"]:checked');
      const sz  = document.querySelector('input[name="rs-sz"]:checked');
      const tr  = document.querySelector('input[name="rs-tr"]:checked');
      if (!ind || !sz || !tr) {
        document.getElementById('rs-dialogue-text').textContent = 'Please answer all 3 questions first.';
        updateMessageAvatar('pb-riskscore-avatar-container', 'error', 2500);
        return;
      }
      const raw   = +ind.value + +sz.value + +tr.value; // 0-9
      const pct   = Math.round(14 + raw * 8);            // 14-86%
      const color = pct >= 60 ? 'var(--danger)' : pct >= 35 ? 'var(--warning)' : 'var(--success,#34D399)';
      const label = pct >= 60 ? 'High exposure — simulations strongly recommended'
                  : pct >= 35 ? 'Moderate exposure — some controls in place'
                  :             'Lower exposure — good hygiene, keep it up';
      
      let reaction = '';
      if (pct >= 60) {
        reaction = getRandomVariant(riskHighPool, 'risk_high');
      } else if (pct >= 35) {
        reaction = getRandomVariant(riskMedPool, 'risk_med');
      } else {
        reaction = getRandomVariant(riskLowPool, 'risk_low');
      }

      document.getElementById('rs-form').style.display = 'none';
      const res = document.getElementById('rs-result');
      const avatarState = pct >= 60 ? 'error' : pct >= 35 ? 'active' : 'success';
      updateMessageAvatar('pb-riskscore-avatar-container', avatarState, 2500);
      res.style.display = 'block';
      document.getElementById('rs-gauge').style.color = color;
      document.getElementById('rs-gauge').textContent = pct + '%';
      document.getElementById('rs-gauge-lbl').textContent = label;
      document.getElementById('rs-gauge-reaction').innerHTML = '🦈 Lure says: <em>"' + esc(reaction) + '"</em>';
      repositionPanel();
    };

    window.rsReset = function() {
      document.getElementById('rs-result').style.display = 'none';
      document.getElementById('rs-form').style.display = 'block';
      document.getElementById('rs-gauge-reaction').textContent = '';
      document.querySelectorAll('.rs-opt').forEach(o => o.classList.remove('selected'));
      document.querySelectorAll('.rs-opt input').forEach(i => i.checked = false);
      document.getElementById('rs-dialogue-text').textContent = "3 quick questions. I'll estimate your organisation's phishing exposure.";
      updateMessageAvatar('pb-riskscore-avatar-container', 'idle');
      repositionPanel();
    };

    document.querySelectorAll('.rs-opt').forEach(opt => {
      opt.addEventListener('click', () => {
        const name = opt.querySelector('input').name;
        document.querySelectorAll(`.rs-opt input[name="${name}"]`)
          .forEach(i => i.closest('.rs-opt').classList.remove('selected'));
        opt.classList.add('selected');
        opt.querySelector('input').checked = true;
      });
    });

    /* ════════════════════════════════════════════════════════
       Proactive Callout Controller
       ════════════════════════════════════════════════════════ */
    const calloutEl = document.getElementById('pb-callout');
    const calloutText = document.getElementById('pb-callout-text');
    const calloutDismiss = document.getElementById('pb-callout-dismiss');

    let calloutTourCallback = null;

    function showCallout(message, tourName = null) {
      if (!calloutEl || !calloutText) return;
      calloutText.textContent = message;

      // Update click cursor and callback if tourName is provided
      calloutEl.style.cursor = tourName ? 'pointer' : 'default';
      calloutTourCallback = tourName ? () => {
        hideCallout();
        startWalkthrough(tourName);
      } : null;

      calloutEl.setAttribute('aria-hidden', 'false');
      // Small delay so CSS transition fires
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          calloutEl.classList.add('pb-show');
        });
      });

      // Show notification badge if panel is closed
      if (!panelOpen) {
        unseenCalloutsCount++;
        updateAvatarBadge();
      }
    }

    function hideCallout() {
      if (!calloutEl) return;
      calloutEl.classList.remove('pb-show');
      calloutEl.setAttribute('aria-hidden', 'true');
      calloutEl.style.cursor = 'default';
      calloutTourCallback = null;
    }

    if (calloutDismiss) {
      calloutDismiss.addEventListener('click', (e) => {
        e.stopPropagation();
        hideCallout();
      });
    }

    if (calloutEl) {
      calloutEl.addEventListener('click', (e) => {
        if (e.target && e.target.id === 'pb-callout-dismiss') return;
        if (calloutTourCallback) {
          calloutTourCallback();
        }
      });
    }

    // Expose for page-level use
    window.lureShowCallout = function(msg, tourName) { showCallout(msg, tourName); };
    window.lureHideCallout = function() { hideCallout(); };
    window.lureIsCalloutShowing = function() {
      return calloutEl && calloutEl.classList.contains('pb-show');
    };
    window.lureIsWalkthroughActive = function() {
      return wtActive || (localStorage.getItem('pb_wt_active') === 'true');
    };
    window.lureHasCompletedTour = function(tourName) {
      loadVisitorProfile();
      return !!(visitorProfile.completedTours && visitorProfile.completedTours[tourName]);
    };
    window.lureOpenWalkthroughDirectly = function() { openWalkthroughDirectly(); };

    /* ════════════════════════════════════════════════════════
       Public Orb State API
       ════════════════════════════════════════════════════════
       window.lureFlashSuccess() — briefly flashes the success
       (green) orb state for ~2.2 s then reverts to idle.

       window.lureSetState(state) — sets orb to any named
       state: 'idle' | 'active' | 'success' | 'error'
       ════════════════════════════════════════════════════════ */
    window.lureFlashSuccess = function () {
      host.className = 'pb-success';
      clearTimeout(window._lureSuccessTimer);
      window._lureSuccessTimer = setTimeout(function () {
        host.className = '';
        if (typeof resetIdleFidgetTimer === 'function') resetIdleFidgetTimer();
      }, 2200);
      if (typeof resetIdleFidgetTimer === 'function') resetIdleFidgetTimer();
    };

    window.lureSetState = function (state) {
      clearTimeout(window._lureSuccessTimer);
      host.className = (state === 'idle') ? '' : 'pb-' + state;
      if (typeof resetIdleFidgetTimer === 'function') resetIdleFidgetTimer();
    };

    /* ════════════════════════════════════════════════════════
       Ask Lure Chat Controller
       ════════════════════════════════════════════════════════ */
    const chatInput = document.getElementById('pb-chat-input');
    const chatSendBtn = document.getElementById('pb-chat-send-btn');
    const chatMessagesList = document.getElementById('pb-chat-messages-list');
    const chatErrorAlert = document.getElementById('pb-chat-error-alert');
    const chatCharCounter = document.getElementById('pb-chat-char-counter');
    const chatTabBtn = panel.querySelector('.pb-tab-btn[data-tab="chat"]');

    let chatHistory = [];
    let chatInitialized = false;

    const contextSuggestions = {
      "marketing/home page": [
        "What is PhishSim.ai?",
        "How do I start a campaign?",
        "Is there a free trial?"
      ],
      "dashboard": [
        "What's a good click-rate?",
        "How do I read this chart?",
        "Why is my click-rate high?"
      ],
      "campaign creation": [
        "What scenario should I choose?",
        "How do I upload targets?",
        "What are delivery modes?"
      ],
      "Threat Analyzer tool": [
        "How do I analyze an email?",
        "What is a threat indicator?",
        "Is this raw email safe?"
      ],
      "Header Analyzer tool": [
        "What does SPF fail mean?",
        "Why does DKIM matter?",
        "How do I check DMARC?"
      ],
      "URL Decoder tool": [
        "Why decode a URL?",
        "What is redirect tracing?",
        "Are shortened URLs safe?"
      ],
      "Password Breach Checker tool": [
        "How does breach check work?",
        "Is my email compromised?",
        "What if my password leaked?"
      ],
      "campaign report": [
        "How do I view clicks?",
        "Who clicked the phishing link?",
        "How to download the report?"
      ],
      "generic": [
        "How does PhishSim work?",
        "How to spot a phishing mail?",
        "What features do you have?"
      ]
    };

    function getPageContext() {
      const currentPath = window.location.pathname.replace(/\/$/, '') || '/';
      
      if (currentPath === '/' || currentPath === '/home') {
        return {
          label: "marketing/home page",
          description: "This is the marketing homepage of PhishSim.ai, highlighting platform features, simulator capabilities, and interactive demonstration sandboxes."
        };
      }
      if (currentPath.startsWith('/dashboard')) {
        return {
          label: "dashboard",
          description: "This is the live dashboard showing security campaign statistics, email click-rate trends, and simulated phishing analysis results."
        };
      }
      if (currentPath.startsWith('/new-campaign')) {
        return {
          label: "campaign creation",
          description: "This is the campaign creator walkthrough, allowing users to define phishing scenarios, target lists, delivery modes, and launch schedules."
        };
      }
      if (currentPath.startsWith('/threat-analyzer')) {
        return {
          label: "Threat Analyzer tool",
          description: "This is the Threat Analyzer sandbox, used for inspecting and analyzing raw email bodies and headers for indicators of malicious intent or phishing."
        };
      }
      if (currentPath.startsWith('/header-analyzer')) {
        return {
          label: "Header Analyzer tool",
          description: "This is the Header Analyzer tool, helping decode technical email routing paths and check SPF, DKIM, and DMARC alignment status."
        };
      }
      if (currentPath.startsWith('/url-decoder')) {
        return {
          label: "URL Decoder tool",
          description: "This is the URL Decoder utility, designed to expand obfuscated links and trace redirect hops to spot malicious destinations safely."
        };
      }
      if (currentPath.startsWith('/password-breach')) {
        return {
          label: "Password Breach Checker tool",
          description: "This is the Password Breach Checker, checking email addresses against public databases of known data breaches and compromised credentials."
        };
      }
      if (currentPath.startsWith('/campaign-report') || currentPath.startsWith('/campaign-emails')) {
        return {
          label: "campaign report",
          description: "This is the detailed metrics page for a specific campaign, highlighting delivery logs, click metrics, and detailed user activity results."
        };
      }
      
      return {
        label: null,
        description: null
      };
    }

    function renderSuggestions() {
      const suggestionsContainer = document.getElementById('pb-chat-suggestions');
      if (!suggestionsContainer) return;

      if (chatHistory.length > 0) {
        suggestionsContainer.style.display = 'none';
        suggestionsContainer.innerHTML = '';
        return;
      }

      const ctx = getPageContext();
      const label = ctx.label || "generic";
      const questions = contextSuggestions[label] || contextSuggestions["generic"];

      suggestionsContainer.innerHTML = '';
      questions.forEach(q => {
        const chip = document.createElement('button');
        chip.type = 'button';
        chip.className = 'pb-chat-suggestion-chip';
        chip.textContent = q;
        chip.addEventListener('click', () => {
          if (chatInput) {
            chatInput.value = q;
            sendMessage();
          }
        });
        suggestionsContainer.appendChild(chip);
      });

      suggestionsContainer.style.display = 'flex';
      repositionPanel();
    }

    // Load from sessionStorage on init
    function loadChatHistory() {
      try {
        const stored = sessionStorage.getItem('pb_chat_history');
        if (stored) {
          chatHistory = JSON.parse(stored);
        }
      } catch (e) {
        console.error('Failed to load chat history', e);
      }
    }

    function saveChatHistory() {
      try {
        sessionStorage.setItem('pb_chat_history', JSON.stringify(chatHistory));
      } catch (e) {
        console.error('Failed to save chat history', e);
      }
    }

    function renderMessages(isNewReply = false) {
      if (!chatMessagesList) return;
      chatMessagesList.innerHTML = '';

      // Always prepend the hardcoded welcome message
      const welcomeRow = document.createElement('div');
      welcomeRow.className = 'pb-chat-msg-row lure';
      welcomeRow.innerHTML = `
        <div class="pb-dialogue-icon">${getLureAvatarHtml('idle')}</div>
        <div class="pb-chat-bubble">Hi! I'm Lure, your AI security mascot. 🦈 Ask me anything about phishing, social engineering, or how to use PhishSim to train your defenses!</div>
      `;
      chatMessagesList.appendChild(welcomeRow);

      chatHistory.forEach((msg, idx) => {
        const row = document.createElement('div');
        row.className = `pb-chat-msg-row ${msg.role === 'user' ? 'user' : 'lure'}`;
        // Simple HTML sanitization to prevent XSS but keep formatting safe
        const safeText = esc(msg.content);
        if (msg.role === 'user') {
          row.innerHTML = `<div class="pb-chat-bubble">${safeText}</div>`;
        } else {
          // If this is the last message and isNewReply is true, show success state briefly
          const isLast = (idx === chatHistory.length - 1);
          const state = (isLast && isNewReply) ? 'success' : 'idle';
          row.innerHTML = `
            <div class="pb-dialogue-icon" ${isLast ? 'id="pb-chat-avatar-last"' : ''}>${getLureAvatarHtml(state)}</div>
            <div class="pb-chat-bubble">${safeText}</div>
          `;
        }
        chatMessagesList.appendChild(row);
      });

      if (isNewReply) {
        setTimeout(() => {
          const lastAvatarContainer = document.getElementById('pb-chat-avatar-last');
          if (lastAvatarContainer) {
            lastAvatarContainer.innerHTML = getLureAvatarHtml('idle');
          }
        }, 2500);
      }

      // Render suggestions
      renderSuggestions();

      // Scroll to bottom
      chatMessagesList.scrollTop = chatMessagesList.scrollHeight;
    }

    function initChat() {
      if (chatInitialized) return;
      chatInitialized = true;
      loadChatHistory();
      renderMessages();
    }

    // Initialize when Chat tab is clicked
    if (chatTabBtn) {
      chatTabBtn.addEventListener('click', () => {
        initChat();
        // Focus the input
        setTimeout(() => chatInput && chatInput.focus(), 100);
      });
    }

    // Character counter and cap enforcement
    if (chatInput) {
      chatInput.addEventListener('input', () => {
        const len = chatInput.value.length;
        if (chatCharCounter) {
          chatCharCounter.textContent = `${len} / 500`;
          if (len > 500) {
            chatCharCounter.style.color = 'var(--danger, #ef4444)';
            chatSendBtn.disabled = true;
            showChatError("Message exceeds the 500-character limit.");
          } else {
            chatCharCounter.style.color = 'var(--text-muted, #4A5568)';
            chatSendBtn.disabled = false;
            hideChatError();
          }
        }
      });

      // Handle Enter and Shift+Enter
      chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          sendMessage();
        }
      });
    }

    if (chatSendBtn) {
      chatSendBtn.addEventListener('click', sendMessage);
    }

    function showChatError(msg) {
      if (chatErrorAlert) {
        chatErrorAlert.textContent = msg;
        chatErrorAlert.style.display = 'block';
      }
    }

    function hideChatError() {
      if (chatErrorAlert) {
        chatErrorAlert.style.display = 'none';
      }
    }

    async function sendMessage() {
      if (!chatInput) return;
      const text = chatInput.value.trim();
      if (!text || text.length > 500 || chatSendBtn.disabled) return;

      // Clear input and counter
      chatInput.value = '';
      if (chatCharCounter) chatCharCounter.textContent = '0 / 500';

      // 1. Add user message
      chatHistory.push({ role: 'user', content: text });
      saveChatHistory();
      renderMessages();
      let isSuccessReply = false;

      // 2. Add Typing indicator with loading text
      const typingRow = document.createElement('div');
      typingRow.className = 'pb-chat-msg-row lure';
      typingRow.id = 'pb-chat-typing-indicator';
      typingRow.innerHTML = `
        <div class="pb-dialogue-icon">${getLureAvatarHtml('active')}</div>
        <div class="pb-chat-bubble" style="display: flex; align-items: center; gap: 8px;">
          <div class="pb-typing-indicator" style="flex-shrink: 0;">
            <span class="pb-typing-dot"></span>
            <span class="pb-typing-dot"></span>
            <span class="pb-typing-dot"></span>
          </div>
          <span id="pb-chat-loading-text" style="font-size: 0.65rem; color: var(--text-secondary,#8CA0B3); font-family: var(--mono);">Lure is thinking...</span>
        </div>
      `;
      chatMessagesList.appendChild(typingRow);
      chatMessagesList.scrollTop = chatMessagesList.scrollHeight;

      let stopChatNarration = null;
      const loadingTextEl = document.getElementById('pb-chat-loading-text');
      if (loadingTextEl) {
        const chatStages = [
          "Lure is thinking...",
          "Drafting response..."
        ];
        stopChatNarration = startLoadingNarration(loadingTextEl, chatStages, 1200, 6000, "Lure is typing... (still processing)");
      }

      // Disable inputs during API call
      chatInput.disabled = true;
      chatSendBtn.disabled = true;
      hideChatError();

      // Flashing mascot active state
      lureSetState('active');

      const ctx = getPageContext();
      try {
        const response = await fetch('/api/lure-chat', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            message: text,
            history: chatHistory.slice(0, -1), // pass history excluding the last message
            page_context: ctx.label || null,
            page_description: ctx.description || null
          })
        });

        const data = await response.json();
        
        // Remove typing indicator & stop narration
        if (stopChatNarration) stopChatNarration();
        const indicator = document.getElementById('pb-chat-typing-indicator');
        if (indicator) indicator.remove();

        if (response.ok && data.success) {
          chatHistory.push({ role: 'assistant', content: data.reply });
          saveChatHistory();
          lureFlashSuccess();
          isSuccessReply = true;
        } else {
          showChatError(data.message || "Something went wrong. Please try again.");
          lureSetState('idle');
        }
      } catch (e) {
        console.error(e);
        if (stopChatNarration) stopChatNarration();
        const indicator = document.getElementById('pb-chat-typing-indicator');
        if (indicator) indicator.remove();
        showChatError("Network error. Unable to reach Lure.");
        lureSetState('idle');
      } finally {
        chatInput.disabled = false;
        chatSendBtn.disabled = false;
        renderMessages(isSuccessReply);
        chatInput.focus();
      }
    }

    // Check if the user just completed a walkthrough and show the custom welcome popover
    function checkCompletedTourUrl() {
      const urlParams = new URLSearchParams(window.location.search);
      if (urlParams.get('completed_tour') === 'true') {
        window.history.replaceState({}, document.title, window.location.pathname);
        setTimeout(() => {
          showTourCompletedPopover();
        }, 500);
      }
    }

    function showTourCompletedPopover() {
      const fvPopover = document.getElementById('pb-first-visit-popover');
      if (!fvPopover) return;
      
      fvPopover.querySelector('.pb-popover-title').textContent = "Tour Completed!";
      fvPopover.querySelector('.pb-popover-text').textContent = "Congratulations on finishing the PhishSim AI tour! You can now sign up to launch real phishing simulation campaigns for your organization, or try out the Live Demo again to explore further.";
      
      const actions = fvPopover.querySelector('.pb-popover-actions');
      if (actions) {
        actions.innerHTML = `
          <button class="pb-popover-btn primary" onclick="window.location.href='/signup'">Sign Up Free</button>
          <button class="pb-popover-btn secondary" onclick="window.location.href='/demo-login'">Try Live Demo</button>
        `;
      }
      
      openFvPopover();
    }
    


    /* ════════════════════════════════════════════════════════
       Global Keyboard Shortcut (Cmd+K / Ctrl+K)
       ════════════════════════════════════════════════════════ */
    document.addEventListener('keydown', (e) => {
      const isK = e.key === 'k' || e.key === 'K';
      const isModifier = e.metaKey || e.ctrlKey;
      if (isK && isModifier) {
        // Do not intercept if focus is inside typing fields
        const activeEl = document.activeElement;
        if (activeEl) {
          const tag = activeEl.tagName.toLowerCase();
          const isContentEditable = activeEl.getAttribute('contenteditable') === 'true' || activeEl.contentEditable === 'true';
          if (tag === 'input' || tag === 'textarea' || isContentEditable) {
            return;
          }
        }

        e.preventDefault();

        // Switch to Ask Lure tab, open panel, and focus chat input
        const chatTab = panel.querySelector('.pb-tab-btn[data-tab="chat"]');
        if (chatTab) {
          chatTab.click();
        }

        if (!panelOpen) {
          openPanel();
        }

        const inputEl = document.getElementById('pb-chat-input');
        if (inputEl) {
          setTimeout(() => {
            inputEl.focus();
          }, 100);
        }
      }
    });

    /* ════════════════════════════════════════════════════════
       Mascot Idle Fidget Timer Controller
       ════════════════════════════════════════════════════════ */
    let idleFidgetTimeout = null;
    let isHoveringAvatar = false;
    const avatarWrap = document.getElementById('pb-avatar-wrap');

    function scheduleNextIdleFidget() {
      clearTimeout(idleFidgetTimeout);
      const delay = Math.floor(Math.random() * (90000 - 45000 + 1)) + 45000;
      idleFidgetTimeout = setTimeout(playIdleFidget, delay);
    }

    function playIdleFidget() {
      const isWtActive = typeof window.lureIsWalkthroughActive === 'function' ? window.lureIsWalkthroughActive() : false;
      const isIdleState = !host.className || host.className === '';
      
      if (!panelOpen && !isWtActive && isIdleState && !isHoveringAvatar) {
        if (avatarWrap) {
          avatarWrap.classList.remove('pb-fidget-active');
          void avatarWrap.offsetWidth; // force reflow
          avatarWrap.classList.add('pb-fidget-active');
          
          setTimeout(() => {
            avatarWrap.classList.remove('pb-fidget-active');
          }, 2500);
        }
      }
      
      scheduleNextIdleFidget();
    }

    window.resetIdleFidgetTimer = function() {
      scheduleNextIdleFidget();
    };

    if (avatar) {
      avatar.addEventListener('mouseenter', () => {
        isHoveringAvatar = true;
        resetIdleFidgetTimer();
      });
      avatar.addEventListener('mouseleave', () => {
        isHoveringAvatar = false;
        resetIdleFidgetTimer();
      });
      avatar.addEventListener('click', () => {
        resetIdleFidgetTimer();
      });
    }

    // Start fidget timer
    resetIdleFidgetTimer();

    checkCompletedTourUrl();

  })();
