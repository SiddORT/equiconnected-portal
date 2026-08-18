import React from 'react';
import styles from './Card.module.css';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  padding?: 'none' | 'sm' | 'md' | 'lg';
  shadow?: 'none' | 'sm' | 'md' | 'lg';
  as?: React.ElementType;
}

export function Card({
  children,
  className = '',
  padding = 'md',
  shadow = 'sm',
  as: Tag = 'div',
}: CardProps) {
  return (
    <Tag
      className={[
        styles.card,
        styles[`card--pad-${padding}`],
        styles[`card--shadow-${shadow}`],
        className,
      ]
        .filter(Boolean)
        .join(' ')}
    >
      {children}
    </Tag>
  );
}

export function CardHeader({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <div className={`${styles.cardHeader} ${className}`}>{children}</div>;
}

export function CardBody({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <div className={`${styles.cardBody} ${className}`}>{children}</div>;
}

export function CardFooter({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <div className={`${styles.cardFooter} ${className}`}>{children}</div>;
}
