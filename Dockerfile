# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Install uv
RUN pip install uv

# Install ffmpeg, mkvtoolnix, Tesseract OCR and build dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    mkvtoolnix \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-fra \
    tesseract-ocr-spa \
    tesseract-ocr-deu \
    tesseract-ocr-ita \
    curl \
    git \
    gcc \
    g++ \
    cmake \
    pkg-config \
    libcairo2-dev \
    libpango1.0-dev \
    libleptonica-dev \
    libtesseract-dev \
    llvm-dev \
    libclang-dev \
    clang \
    && rm -rf /var/lib/apt/lists/*

# Install Rust for building subtile-ocr
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Build and install subtile-ocr from source
RUN cargo install subtile-ocr && \
    cp /root/.cargo/bin/subtile-ocr /usr/local/bin/subtile-ocr && \
    chmod 755 /usr/local/bin/subtile-ocr

# Set the working directory in the container
WORKDIR /app

# Copy only necessary files for the application
COPY pyproject.toml Makefile ./
COPY src/ ./src/
COPY test/ ./test/

# Set PYTHONPATH before installing/running
ENV PYTHONPATH=/app

# Install any needed packages specified in requirements.txt
RUN apt-get update && apt-get install -y make libatomic1 && \
    make install && \
    make lint && \
    make check && \
    make test-unit

# Create non-root user with UID 1000 and GID 1000
RUN groupadd -r -g 1000 appgroup && useradd -r -u 1000 -g appgroup appuser

RUN mkdir -p /home/appuser/.cache && chown appuser:appgroup /home/appuser/.cache

# Set ownership of application directory
RUN chown -R appuser:appgroup /app

# Fix permissions for cargo binaries (installed as root)
RUN chmod -R 755 /root/.cargo/bin

# Switch to non-root user
USER 1000:1000

# Make port 8001 available to the world outside this container
EXPOSE 8001

# Run app via the template Makefile target (which itself uses uv)
CMD ["make", "run"]
