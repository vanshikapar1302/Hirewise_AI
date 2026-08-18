document.addEventListener('DOMContentLoaded', () => {
    // DOM elements
    const videoPreview = document.getElementById('webcam-preview');
    const startBtn = document.getElementById('start-rec-btn');
    const stopBtn = document.getElementById('stop-rec-btn');
    const submitBtn = document.getElementById('submit-ans-btn');
    const timerDisplay = document.getElementById('timer-display');
    const recordingStatus = document.getElementById('recording-status');
    const transcriptText = document.getElementById('transcript-text');
    const waveBars = document.querySelectorAll('.wave-bar');
    const spinnerOverlay = document.getElementById('spinner-overlay');
    const gazeIndicator = document.getElementById('gaze-indicator');

    // State variables
    let stream = null;
    let audioRecorder = null;
    let videoRecorder = null;
    let audioChunks = [];
    let videoChunks = [];
    let audioBlob = null;
    let videoBlob = null;
    
    let timerInterval = null;
    let recordDuration = 0; // in seconds
    let speechRecognition = null;
    let finalTranscript = '';
    
    // Interview Metadata (Injected in template)
    const sessionId = parseInt(document.getElementById('meta-session-id').value);
    let sessionTimerInterval = null;
    let sessionElapsed = parseInt(sessionStorage.getItem('interview_session_elapsed_' + sessionId) || '0');
    
    let radarChart = null;

    // 1. Overall Session Timer
    function startSessionTimer() {
        const sessionTimerDisplay = document.getElementById('session-timer-display');
        if (!sessionTimerDisplay) return;
        
        function updateSessionTimerUI() {
            const mins = String(Math.floor(sessionElapsed / 60)).padStart(2, '0');
            const secs = String(sessionElapsed % 60).padStart(2, '0');
            sessionTimerDisplay.textContent = `${mins}:${secs}`;
        }
        
        updateSessionTimerUI();
        
        sessionTimerInterval = setInterval(() => {
            sessionElapsed++;
            sessionStorage.setItem('interview_session_elapsed_' + sessionId, sessionElapsed);
            updateSessionTimerUI();
        }, 1000);
    }

    // 2. Device and Network status monitoring
    function updateStatusIndicators() {
        const cameraStatus = document.getElementById('status-camera');
        const micStatus = document.getElementById('status-mic');
        const networkStatus = document.getElementById('status-network');
        
        // Network Check
        if (networkStatus) {
            if (navigator.onLine) {
                networkStatus.textContent = 'Online';
                networkStatus.className = 'badge bg-success-light text-success';
            } else {
                networkStatus.textContent = 'Offline';
                networkStatus.className = 'badge bg-danger-light text-danger';
            }
        }
        
        // Camera & Mic Track Checks
        if (stream) {
            const videoTracks = stream.getVideoTracks();
            const audioTracks = stream.getAudioTracks();
            
            const isCamActive = videoTracks.length > 0 && videoTracks.every(t => t.readyState === 'live' && t.enabled);
            const isMicActive = audioTracks.length > 0 && audioTracks.every(t => t.readyState === 'live' && t.enabled);
            
            if (cameraStatus) {
                if (isCamActive) {
                    cameraStatus.textContent = 'Cam OK';
                    cameraStatus.className = 'badge bg-success-light text-success';
                } else {
                    cameraStatus.textContent = 'Cam Off';
                    cameraStatus.className = 'badge bg-danger-light text-danger';
                }
            }
            
            if (micStatus) {
                if (isMicActive) {
                    micStatus.textContent = 'Mic OK';
                    micStatus.className = 'badge bg-success-light text-success';
                } else {
                    micStatus.textContent = 'Mic Off';
                    micStatus.className = 'badge bg-danger-light text-danger';
                }
            }
        } else {
            if (cameraStatus) {
                cameraStatus.textContent = 'Cam Blocked';
                cameraStatus.className = 'badge bg-danger-light text-danger';
            }
            if (micStatus) {
                micStatus.textContent = 'Mic Blocked';
                micStatus.className = 'badge bg-danger-light text-danger';
            }
        }
    }

    // 3. Fullscreen Mode Toggle
    const fullscreenBtn = document.getElementById('fullscreen-btn');
    if (fullscreenBtn) {
        fullscreenBtn.addEventListener('click', () => {
            const fsContainer = document.documentElement;
            const icon = document.getElementById('fullscreen-icon');
            
            if (!document.fullscreenElement) {
                fsContainer.requestFullscreen().then(() => {
                    if (icon) {
                        icon.className = 'bi bi-fullscreen-exit';
                    }
                }).catch(err => {
                    console.error(`Error attempting to enable fullscreen mode: ${err.message}`);
                });
            } else {
                document.exitFullscreen().then(() => {
                    if (icon) {
                        icon.className = 'bi bi-fullscreen';
                    }
                });
            }
        });
    }

    // 4. Overall progression bar updates
    function updateOverallProgressBar(currNum, totalNum) {
        const overallPb = document.getElementById('overall-progress-bar');
        const overallPt = document.getElementById('overall-progress-text');
        if (!overallPb) return;
        
        currNum = parseInt(currNum);
        totalNum = parseInt(totalNum) || 5;
        
        const progressPct = Math.round(((currNum - 1) / totalNum) * 100);
        overallPb.style.width = `${progressPct}%`;
        overallPb.setAttribute('aria-valuenow', progressPct);
        if (overallPt) {
            overallPt.textContent = `${progressPct}% Complete (Question ${currNum} of ${totalNum})`;
        }
    }

    // Initialize timers and status indicators
    startSessionTimer();
    window.addEventListener('online', updateStatusIndicators);
    window.addEventListener('offline', updateStatusIndicators);
    setInterval(updateStatusIndicators, 2500);

    // Initialize progression bar
    const initialCurrNum = document.getElementById('meta-current-num').value;
    const initialTotalNum = document.getElementById('meta-total-num').value;
    updateOverallProgressBar(initialCurrNum, initialTotalNum);

    // Helper to update live dashboard metrics
    function updateDashboard(data) {
        if (!data.is_adaptive) return;
        
        // Update competency level badge
        const lvlBadge = document.getElementById('dash-competency-level');
        if (lvlBadge) {
            lvlBadge.textContent = data.overall_level;
            lvlBadge.className = 'badge ' + (
                data.overall_level === 'Beginner' ? 'bg-info' :
                data.overall_level === 'Intermediate' ? 'bg-warning text-dark' : 'bg-success'
            );
        }
        
        // Update difficulty mode badge
        const diffBadge = document.getElementById('dash-difficulty');
        if (diffBadge) {
            diffBadge.textContent = data.current_difficulty;
            diffBadge.className = 'badge ' + (
                data.current_difficulty === 'Easy' ? 'bg-success' :
                data.current_difficulty === 'Medium' ? 'bg-warning text-dark' : 'bg-danger'
            );
        }
        
        // Update completion progression bar
        const pb = document.getElementById('dash-progress-bar');
        const pt = document.getElementById('dash-progress-text');
        if (pb) pb.style.width = `${data.completion_percentage}%`;
        if (pt) pt.textContent = `${data.completion_percentage}% Complete`;
        
        // Update individual skill progress bars
        const barsContainer = document.getElementById('dash-skills-bars');
        if (barsContainer && data.skill_states) {
            barsContainer.innerHTML = '';
            for (const [skill, state] of Object.entries(data.skill_states)) {
                const barHtml = `
                    <div class="mb-1">
                        <div class="d-flex justify-content-between small mb-1 text-white">
                            <span class="fw-semibold">${skill} (${state.level})</span>
                            <span>${state.score}%</span>
                        </div>
                        <div class="progress" style="height: 6px; background-color: rgba(255,255,255,0.1); border-radius: 3px;">
                            <div class="progress-bar bg-primary" role="progressbar" style="width: ${state.score}%" aria-valuenow="${state.score}" aria-valuemin="0" aria-valuemax="100"></div>
                        </div>
                    </div>
                `;
                barsContainer.insertAdjacentHTML('beforeend', barHtml);
            }
        }
        
        // Update weak skill indicators list
        const wsList = document.getElementById('dash-weak-skills');
        if (wsList) {
            wsList.innerHTML = '';
            if (data.weak_skills && data.weak_skills.length > 0) {
                data.weak_skills.forEach(skill => {
                    const li = document.createElement('li');
                    li.className = 'list-group-item bg-transparent text-warning border-0 p-0 mb-1 small';
                    li.innerHTML = `<i class="bi bi-exclamation-triangle-fill me-1"></i> ${skill}`;
                    wsList.appendChild(li);
                });
            } else {
                wsList.innerHTML = '<li class="list-group-item bg-transparent text-muted border-0 p-0 small italic">No critical weak skills detected.</li>';
            }
        }
        
        // Update radar chart points
        if (radarChart && data.skill_states) {
            radarChart.data.labels = Object.keys(data.skill_states);
            radarChart.data.datasets[0].data = Object.values(data.skill_states).map(s => s.score);
            radarChart.update();
        }
    }

    // Initialize Chart.js Radar Chart on load
    if (window.isAdaptive) {
        const initialStates = window.initialSkillStates || {};
        const labels = Object.keys(initialStates);
        const scores = Object.values(initialStates).map(s => s.score);
        
        const canvas = document.getElementById('liveRadarChart');
        if (canvas) {
            radarChart = new Chart(canvas.getContext('2d'), {
                type: 'radar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Competency',
                        data: scores,
                        backgroundColor: 'rgba(99, 102, 241, 0.2)',
                        borderColor: 'rgba(99, 102, 241, 1)',
                        pointBackgroundColor: 'rgba(99, 102, 241, 1)',
                        borderWidth: 2
                    }]
                },
                options: {
                    scales: {
                        r: {
                            angleLines: { color: 'rgba(255, 255, 255, 0.1)' },
                            grid: { color: 'rgba(255, 255, 255, 0.08)' },
                            pointLabels: { color: '#cbd5e1', font: { size: 10, weight: '600' } },
                            ticks: { display: false },
                            suggestedMin: 0,
                            suggestedMax: 100
                        }
                    },
                    plugins: {
                        legend: { display: false }
                    }
                }
            });
        }
        
        // Populate initial UI elements
        updateDashboard({
            is_adaptive: true,
            overall_level: 'Intermediate',
            current_difficulty: 'Medium',
            completion_percentage: 0,
            skill_states: initialStates,
            weak_skills: Object.keys(initialStates).filter(k => initialStates[k].score < 50.0)
        });
    }

    // Initialize Webcam and Microphone Streams
    async function initCamera() {
        try {
            stream = await navigator.mediaDevices.getUserMedia({
                video: { width: 640, height: 480, facingMode: 'user' },
                audio: true
            });
            videoPreview.srcObject = stream;
            
            // Enable start recording button
            startBtn.disabled = false;
            if (recordingStatus) recordingStatus.textContent = 'Ready to Record';
            updateStatusIndicators();
        } catch (err) {
            console.error('Error accessing camera/microphone:', err);
            if (recordingStatus) {
                recordingStatus.textContent = 'Camera/Mic blocked. Please allow permissions.';
                recordingStatus.className = 'text-danger fw-bold';
            }
            updateStatusIndicators();
            alert('Could not access your camera or microphone. Please check your browser permissions.');
        }
    }

    // Setup Web Speech Recognition for Real-time Feedback
    function initSpeechRecognition() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (SpeechRecognition) {
            speechRecognition = new SpeechRecognition();
            speechRecognition.continuous = true;
            speechRecognition.interimResults = true;
            speechRecognition.lang = 'en-US';

            speechRecognition.onresult = (event) => {
                let interimTranscript = '';
                for (let i = event.resultIndex; i < event.results.length; ++i) {
                    if (event.results[i].isFinal) {
                        finalTranscript += event.results[i][0].transcript + ' ';
                    } else {
                        interimTranscript += event.results[i][0].transcript;
                    }
                }
                
                // Show real-time transcript on screen
                transcriptText.innerHTML = `<strong>Transcript:</strong> ${finalTranscript} <span class="text-muted">${interimTranscript}</span>`;
            };

            speechRecognition.onerror = (event) => {
                console.warn('Speech recognition error:', event.error);
            };
        } else {
            console.log('Web Speech API is not supported in this browser. Fallback will rely on backend transcribers.');
            transcriptText.innerHTML = '<em>Real-time transcription is not supported in this browser (Recommended: Chrome). Speech will be processed on submit.</em>';
        }
    }

    // Call initializers
    initCamera();
    initSpeechRecognition();

    // Start Recording
    startBtn.addEventListener('click', () => {
        if (!stream) return;
        
        audioChunks = [];
        videoChunks = [];
        finalTranscript = '';
        recordDuration = 0;
        
        // Start timers
        timerDisplay.textContent = '00:00';
        timerInterval = setInterval(() => {
            recordDuration++;
            const mins = String(Math.floor(recordDuration / 60)).padStart(2, '0');
            const secs = String(recordDuration % 60).padStart(2, '0');
            timerDisplay.textContent = `${mins}:${secs}`;
            
            // Auto stop at 2 minutes to prevent huge uploads
            if (recordDuration >= 120) {
                stopBtn.click();
            }
        }, 1000);

        // Configure recorders
        const audioStream = new MediaStream(stream.getAudioTracks());
        
        audioRecorder = new MediaRecorder(audioStream, { mimeType: 'audio/webm' });
        videoRecorder = new MediaRecorder(stream, { mimeType: 'video/webm' });

        audioRecorder.ondataavailable = (e) => {
            if (e.data && e.data.size > 0) audioChunks.push(e.data);
        };
        
        videoRecorder.ondataavailable = (e) => {
            if (e.data && e.data.size > 0) videoChunks.push(e.data);
        };

        audioRecorder.onstop = () => {
            audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
        };
        
        videoRecorder.onstop = () => {
            videoBlob = new Blob(videoChunks, { type: 'video/webm' });
            submitBtn.disabled = false;
        };

        // Start recorders
        audioRecorder.start();
        videoRecorder.start();

        // Start Web Speech API
        if (speechRecognition) {
            speechRecognition.start();
        }

        // Toggle UI states
        startBtn.classList.add('d-none');
        stopBtn.classList.remove('d-none');
        submitBtn.disabled = true;
        recordingStatus.textContent = 'Recording active... Speak now';
        recordingStatus.className = 'text-danger fw-bold';
        
        // Start speech waves animation
        waveBars.forEach(bar => bar.classList.add('active'));
        if (gazeIndicator) {
            gazeIndicator.textContent = 'TRACKING GAZE';
            gazeIndicator.className = 'gaze-status-indicator bg-primary';
        }
    });

    // Stop Recording
    stopBtn.addEventListener('click', () => {
        clearInterval(timerInterval);
        
        if (audioRecorder && audioRecorder.state !== 'inactive') {
            audioRecorder.stop();
        }
        if (videoRecorder && videoRecorder.state !== 'inactive') {
            videoRecorder.stop();
        }
        if (speechRecognition) {
            speechRecognition.stop();
        }

        // Toggle UI states
        stopBtn.classList.add('d-none');
        startBtn.classList.remove('d-none');
        startBtn.textContent = 'Re-record Answer';
        recordingStatus.textContent = 'Recording stopped. You can submit now or re-record.';
        recordingStatus.className = 'text-success fw-bold';
        
        // Stop speech waves animation
        waveBars.forEach(bar => bar.classList.remove('active'));
        if (gazeIndicator) {
            gazeIndicator.textContent = 'GAZE COMPLETE';
            gazeIndicator.className = 'gaze-status-indicator bg-success';
        }
    });

    // Submit Answer (AJAX)
    submitBtn.addEventListener('click', async () => {
        if (!audioBlob || !videoBlob) {
            alert('Please record an answer first.');
            return;
        }

        // Show spinner overlay
        spinnerOverlay.classList.remove('d-none');

        const formData = new FormData();
        formData.append('session_id', sessionId);
        formData.append('duration', recordDuration);
        formData.append('browser_transcript', finalTranscript.trim());
        
        const currentIsFollowUp = document.getElementById('meta-is-follow-up').value === 'true';
        const currentQuestionText = document.getElementById('meta-question-text').value;
        formData.append('is_follow_up', currentIsFollowUp);
        formData.append('question_text', currentQuestionText);
        
        // Append blobs as files
        formData.append('audio', audioBlob, 'response.webm');
        formData.append('video', videoBlob, 'gaze.webm');

        try {
            const response = await fetch('/interview/submit_answer', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                let errorDetails = `Server returned status ${response.status}`;
                try {
                    const errorJson = await response.json();
                    if (errorJson && errorJson.error) {
                        errorDetails = `[Stage: ${errorJson.stage || 'Processing'}] ${errorJson.error}`;
                    }
                } catch (e) {}
                throw new Error(errorDetails);
            }

            const data = await response.json();
            
            if (data.success) {
                // If the entire interview is completed
                if (data.is_done) {
                    sessionStorage.removeItem('interview_session_elapsed_' + sessionId); // Clean session timer
                    window.location.href = `/interview/finalize/${sessionId}`;
                } else {
                    // Update dashboard states dynamically
                    updateDashboard(data);
                    
                    // Update question progress badge in header
                    const progressBadge = document.getElementById('question-progress-badge');
                    if (progressBadge) {
                        if (data.is_follow_up_next) {
                            progressBadge.className = 'badge bg-danger mb-2 px-3 py-1.5 fw-semibold';
                            progressBadge.style.borderRadius = '12px';
                            progressBadge.innerHTML = '<i class="bi bi-robot me-1"></i> AI Follow-Up Question';
                        } else {
                            progressBadge.className = 'badge bg-primary mb-2 px-3 py-1.5 fw-semibold';
                            progressBadge.style.borderRadius = '12px';
                            progressBadge.innerHTML = `Progress: Question <span id="current-question-num">${data.next_num}</span> of <span id="total-question-num">${data.total_num || 5}</span>`;
                        }
                    }
                    
                    // Update hidden metadata and overall progression bar
                    document.getElementById('meta-current-num').value = data.next_num;
                    document.getElementById('meta-total-num').value = data.total_num || 5;
                    updateOverallProgressBar(data.next_num, data.total_num || 5);
                    
                    // Replace active question details dynamically in DOM and inputs
                    document.getElementById('question-text-heading').textContent = data.next_question_text;
                    document.getElementById('meta-question-text').value = data.next_question_text;
                    document.getElementById('meta-is-follow-up').value = data.is_follow_up_next ? 'true' : 'false';
                    
                    // Reset recorder status and button controls
                    audioBlob = null;
                    videoBlob = null;
                    audioChunks = [];
                    videoChunks = [];
                    finalTranscript = '';
                    
                    submitBtn.disabled = true;
                    startBtn.classList.remove('d-none');
                    startBtn.textContent = 'Start Recording';
                    stopBtn.classList.add('d-none');
                    
                    timerDisplay.textContent = '00:00';
                    recordingStatus.textContent = 'Ready to Record';
                    recordingStatus.className = 'alert alert-secondary py-2 px-3 small border-0 text-center';
                    transcriptText.innerHTML = '<strong>Transcript:</strong> <em>[Speech transcript will display here in real-time as you speak...]</em>';
                    
                    // Hide spinner overlay
                    spinnerOverlay.classList.add('d-none');
                }
            } else {
                let errorMsg = 'Unknown error';
                if (data.stage && data.error) {
                    errorMsg = `[Stage: ${data.stage}] ${data.error}`;
                } else if (data.error) {
                    errorMsg = data.error;
                }
                alert(`Analysis Failed: ${errorMsg}\nHeuristic fallback evaluations will be utilized.`);
                spinnerOverlay.classList.add('d-none');
            }
        } catch (err) {
            console.error('Submission error:', err);
            alert(`Analysis Pipeline Error:\n${err.message || err}\n\nCheck your backend terminal logs for detailed stack traces.`);
            spinnerOverlay.classList.add('d-none');
        }
    });
});
