class RainChar {
  constructor(font, charSize, chars, bg, fg) {
    // Defining the parameters
    this.font = font;
    this.charSize = charSize;
    this.chars = chars;
    this.bg = bg;
    this.fg = fg;

    // Setting up the canvas
    const canvas = document.getElementById("rain-effect");
    this.context = canvas.getContext("2d");
    this.size = [canvas.offsetWidth, canvas.offsetHeight];
    canvas.width = this.size[0];
    canvas.height = this.size[1];

    this.context.fillStyle = this.bg;
    this.context.fillRect(0, 0, ...this.size);

    // Creating the particles array
    this.particles = [];
    const particleCount =
      (this.size[0] * this.size[1]) / this.charSize ** 2 / 10;

    for (let i = 0; i < particleCount; i++) {
      this.particles.push(this.newParticle());
    }
  }

  newParticle() {
    return {
      x: Math.random() * this.size[0],
      y: -Math.random() * this.size[1] * 2,
      size: Math.floor(
        Math.random() * (this.charSize * 2 - this.charSize / 2) +
          this.charSize / 2
      )
    };
  }

  drawParticles() {
    this.context.fillStyle = this.fg;
    this.particles.forEach((particle) => {
      this.context.font = `${particle.size}px ${this.font}`;
      const randomChar = this.chars[
        Math.floor(Math.random() * this.chars.length)
      ];
      this.context.fillText(randomChar, particle.x, particle.y);
    });
  }

  updateParticles() {
    this.particles.forEach((particle) => {
      if (particle.y > this.size[1]) {
        Object.assign(particle, this.newParticle());
      } else {
        particle.y += particle.size;
      }
    });
  }

  clearCanvas() {
    this.context.globalAlpha = 0.25;
    this.context.fillStyle = this.bg;
    this.context.fillRect(0, 0, ...this.size);
    this.context.globalAlpha = 1;
  }

  play() {
    this.clearCanvas();
    this.drawParticles();
    this.updateParticles();
    setTimeout(() => {
      this.play();
    }, 50);
  }
}

const chars = "ABCDEFGHIJKLMNOPRSTUVWXYZ";
const rain = new RainChar("monospace", 10, chars, "#ff6a00", "#fff9f197");
rain.play();