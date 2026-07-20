import React, { useState } from 'react';

import { CaptureStep } from './steps/CaptureStep';
import { IntakeStep1 } from './steps/IntakeStep1';
import { IntakeStep2 } from './steps/IntakeStep2';
import { IntakeStep3 } from './steps/IntakeStep3';
import { ProcessingStep } from './steps/ProcessingStep';
import { CapturedImage, IntakeData } from './types';

type Step = 'intake1' | 'intake2' | 'intake3' | 'capture' | 'processing';

/**
 * Linear wizard, no back-navigation — mirrors the web app's flow
 * (frontend/src/main.js's routes.md: home -> intake -> intake-step2 ->
 * intake-optional -> capture -> processing -> plan). Runs once, before the
 * tab bar exists (see App.tsx: shown only when the signed-in user has zero
 * sessions yet).
 */
export function OnboardingFlow({ onComplete }: { onComplete: () => void }) {
  const [step, setStep] = useState<Step>('intake1');
  const [intake, setIntake] = useState<Partial<IntakeData>>({});
  const [image, setImage] = useState<CapturedImage | null>(null);

  switch (step) {
    case 'intake1':
      return (
        <IntakeStep1
          initialGoal={intake.goal}
          initialDays={intake.days_per_week}
          onNext={(patch) => {
            setIntake((prev) => ({ ...prev, ...patch }));
            setStep('intake2');
          }}
        />
      );

    case 'intake2':
      return (
        <IntakeStep2
          initialExperience={intake.experience}
          initialDuration={intake.session_duration}
          onNext={(patch) => {
            setIntake((prev) => ({ ...prev, ...patch }));
            setStep('intake3');
          }}
        />
      );

    case 'intake3':
      return (
        <IntakeStep3
          onNext={(patch) => {
            setIntake((prev) => ({ ...prev, ...patch }));
            setStep('capture');
          }}
        />
      );

    case 'capture':
      return (
        <CaptureStep
          onNext={(captured) => {
            setImage(captured);
            setStep('processing');
          }}
        />
      );

    case 'processing':
      // intake is guaranteed complete by this point (steps 1-2 require
      // their fields before advancing) and image is set right before this
      // step is reached — the casts reflect that, not an unchecked guess.
      return (
        <ProcessingStep
          intake={intake as IntakeData}
          image={image as CapturedImage}
          onComplete={onComplete}
          onRetry={() => setStep('capture')}
        />
      );
  }
}
