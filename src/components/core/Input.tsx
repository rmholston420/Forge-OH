import React from 'react';
import styles from './Input.module.css';

export type InputVariant = 'text' | 'search' | 'path' | 'secret';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  variant?: InputVariant;
  label?: string;
  error?: string;
  hint?: string;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>((
  { variant = 'text', label, error, hint, className = '', id, ...rest },
  ref
) => {
  const inputId = id ?? (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);
  const classes = [
    styles.input,
    styles[`input--${variant}`],
    error ? styles['input--error'] : '',
    className,
  ].filter(Boolean).join(' ');

  return (
    <div className={styles.wrapper}>
      {label && <label htmlFor={inputId} className={styles.label}>{label}</label>}
      <input
        ref={ref}
        id={inputId}
        type={variant === 'secret' ? 'password' : 'text'}
        className={classes}
        aria-describedby={error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined}
        aria-invalid={!!error}
        {...rest}
      />
      {hint && !error && <span id={`${inputId}-hint`} className={styles.hint}>{hint}</span>}
      {error && <span id={`${inputId}-error`} className={styles.error} role="alert">{error}</span>}
    </div>
  );
});

Input.displayName = 'Input';
